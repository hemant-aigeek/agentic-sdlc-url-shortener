"""The orchestration engine (ADR-005, ADR-007, ADR-008, ADR-009).

The engine is stateless between calls: every public method loads the run from
the store, acts, and persists. That is what makes a run resumable from
another process and inspectable while it waits at a gate.

Execution model
---------------
``run()`` loops over *batches*. A batch is the set of stages whose
dependencies are satisfied; agent-owned stages in a batch execute
concurrently on a thread pool, each inside its own retry/timeout/fallback
loop. When a human-owned stage becomes ready the loop opens the gate, moves
the run to a WAITING state and returns — nothing but ``decide()`` can move it
past that point. Terminal outcomes are deterministic: COMPLETED, REJECTED,
FAILED or SAFE_STOPPED with a recorded reason.

Thread safety: worker threads only call agents and the locked ``_persist``
helpers; the store is never touched outside ``self._lock``.
"""

from __future__ import annotations

import secrets
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from agentic_sdlc.config import Settings
from agentic_sdlc.errors import (
    FailureKind,
    GateRequiredError,
    IllegalTransitionError,
    StageError,
    WorkflowNotFoundError,
)
from agentic_sdlc.orchestration.agents.base import AgentRegistry, StageResult
from agentic_sdlc.orchestration.context import ArtifactRef, RunContext
from agentic_sdlc.orchestration.events import ActorType, AuditEvent, EventKind
from agentic_sdlc.orchestration.graph import StageSpec, WorkflowGraph
from agentic_sdlc.orchestration.metrics import compute_run_metrics
from agentic_sdlc.orchestration.states import (
    RunState,
    StageState,
    assert_run_transition,
    assert_stage_transition,
)
from agentic_sdlc.orchestration.store import (
    ArtifactRecord,
    DecisionRecord,
    EdgeRecord,
    MetricsSnapshot,
    ReplanRecord,
    RunRecord,
    StageRecord,
    WorkflowStore,
)
from agentic_sdlc.telemetry.logging import bind, get_logger, unbind

Planner = Callable[[RunContext], WorkflowGraph]
log = get_logger(__name__)


def new_run_id(now: datetime) -> str:
    return f"{int(now.timestamp() * 1000):012x}{secrets.token_hex(7)}"


@dataclass
class _Loaded:
    run: RunRecord
    stages: dict[str, StageRecord]
    graph: WorkflowGraph

    @property
    def ctx(self) -> RunContext:
        return self.run.context

    def states(self) -> dict[str, StageState]:
        return {name: s.state for name, s in self.stages.items()}


@dataclass
class _Outcome:
    stage: str
    state: StageState
    safe_stop_reason: str | None = None


class Engine:
    def __init__(
        self,
        *,
        store: WorkflowStore,
        agents: AgentRegistry,
        planners: dict[str, Planner],
        settings: Settings,
        policy_version: str = "1.0.0",
        clock: Callable[[], datetime] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_workers: int | None = None,
    ) -> None:
        self._store = store
        self._agents = agents
        self._planners = planners
        self._settings = settings
        self._policy_version = policy_version
        self._clock = clock or (lambda: datetime.now(UTC))
        self._sleep = sleep
        self._max_workers = max_workers or settings.max_parallel_stages
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ public

    def start(
        self,
        *,
        title: str,
        requirement: str,
        scope: str,
        planner: str = "sdlc",
        data: dict[str, Any] | None = None,
    ) -> str:
        now = self._clock()
        run_id = new_run_id(now)
        ctx = RunContext(
            run_id=run_id,
            title=title,
            scope=scope,
            requirement_raw=requirement,
            policy_version=self._policy_version,
            planner=planner,
            workspace=str(self._settings.runs_dir / run_id / "workspace"),
            data=dict(data or {}),
        )
        graph = self._build_graph(ctx)
        run = RunRecord(
            id=run_id,
            title=title,
            scope=scope,
            state=RunState.CREATED,
            requirement_raw=requirement,
            requirement_version=1,
            policy_version=self._policy_version,
            graph_version=1,
            context=ctx,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._store.create_run(run)
            self._persist_graph(run, graph, version=1)
            self._emit(
                run_id,
                EventKind.RUN_CREATED,
                ActorType.SYSTEM,
                target="run",
                result=RunState.CREATED.value,
                reason=f"scope={scope} planner={planner}",
                data={"graph": graph.to_dict(), "policy_version": self._policy_version},
            )
        log.info("run_created", run_id=run_id, scope=scope, stages=graph.names())
        return run_id

    def run(self, run_id: str, *, max_batches: int | None = None) -> RunRecord:
        """Advance the run until it waits for a human, terminates, or ``max_batches`` elapse."""
        loaded = self._load(run_id)
        bind(run_id=run_id)
        try:
            if loaded.run.state is RunState.CREATED:
                self._set_run_state(loaded, RunState.RUNNING, event=EventKind.RUN_STARTED)
            if loaded.run.state is RunState.SUSPENDED:
                self._set_run_state(loaded, RunState.RUNNING, event=EventKind.RUN_RESUMED)
            batches = 0
            while loaded.run.state is RunState.RUNNING:
                if self._gate_timed_out(loaded):
                    break
                progressed = self._tick(loaded)
                if not progressed:
                    break
                batches += 1
                if (
                    max_batches is not None
                    and batches >= max_batches
                    and loaded.run.state is RunState.RUNNING
                ):
                    self._set_run_state(
                        loaded,
                        RunState.SUSPENDED,
                        event=EventKind.RUN_SUSPENDED,
                        reason="max_batches reached",
                    )
            return loaded.run
        finally:
            unbind("run_id")

    def decide(
        self,
        run_id: str,
        *,
        gate: str,
        actor: str,
        decision: str,
        reason: str,
        payload: dict[str, Any] | None = None,
    ) -> RunRecord:
        """The only path past a human gate (FR-G01..G05, ADR-007)."""
        payload = dict(payload or {})
        loaded = self._load(run_id)
        run, ctx = loaded.run, loaded.ctx
        if not run.state.is_waiting:
            raise GateRequiredError(f"run is {run.state.value}, not waiting at a gate")
        spec = loaded.graph.stage(gate) if gate in loaded.graph.names() else None
        stage = loaded.stages.get(gate)
        if spec is None or stage is None or not spec.is_gate or stage.state is not StageState.READY:
            raise GateRequiredError(f"gate {gate!r} is not open on this run")
        if self._gate_timed_out(loaded):
            raise GateRequiredError("gate timed out; run has been safe-stopped")
        if decision not in {"approve", "reject", "clarify"}:
            raise GateRequiredError("decision must be approve, reject or clarify")
        if decision == "clarify" and spec.gate_kind != "clarification":
            raise GateRequiredError(f"gate {gate!r} does not accept clarifications")

        now = self._clock()
        with self._lock:
            record = DecisionRecord(
                run_id=run_id,
                gate=gate,
                actor=actor,
                decision=decision,
                reason=reason,
                payload=payload,
                artifact_version=ctx.requirement_version,
                decided_at=now,
            )
            self._store.save_decision(record)
            ctx.decisions.append(
                {
                    "gate": gate,
                    "actor": actor,
                    "decision": decision,
                    "reason": reason,
                    "payload": payload,
                    "requirement_version": ctx.requirement_version,
                    "decided_at": now.isoformat(),
                }
            )
            self._emit(
                run_id,
                EventKind.DECISION_RECORDED,
                ActorType.HUMAN,
                stage=gate,
                target=f"gate:{gate}",
                result=decision,
                reason=reason,
                data={"actor": actor, "payload": payload},
            )
            if decision == "approve":
                self._finish_stage(
                    loaded, gate, StageState.SUCCEEDED, output={"decision": "approve", **payload}
                )
                self._set_run_state(loaded, RunState.RUNNING)
            elif decision == "reject":
                self._finish_stage(
                    loaded, gate, StageState.FAILED, failure_kind="REJECTED", error=reason
                )
                self._compensate(loaded, reason=f"rejected at {gate}")
                self._set_run_state(
                    loaded,
                    RunState.REJECTED,
                    event=EventKind.RUN_REJECTED,
                    reason=f"rejected at {gate}: {reason}",
                    terminal_reason=f"REJECTED at {gate}: {reason}",
                )
            else:  # clarify
                self._finish_stage(
                    loaded, gate, StageState.SUCCEEDED, output={"decision": "clarify", **payload}
                )
                ctx.requirement_version += 1
                run.requirement_version = ctx.requirement_version
                ctx.data.setdefault("clarifications", []).append(
                    {"gate": gate, "actor": actor, "reason": reason, **payload}
                )
                ctx.data.update(payload.get("data_updates", {}))
                self._set_run_state(loaded, RunState.REPLANNING)
                self._replan(loaded, trigger=f"clarification at {gate}", from_stages={gate})
                self._set_run_state(loaded, RunState.RUNNING)
            self._save_run(loaded)
        return loaded.run

    def resume(self, run_id: str) -> RunRecord:
        """Continue a run after interruption from persisted state (FR-O13)."""
        loaded = self._load(run_id)
        run = loaded.run
        if run.state.is_terminal:
            return run
        with self._lock:
            interrupted = [s for s in loaded.stages.values() if s.state is StageState.RUNNING]
            for stage in interrupted:
                spec = loaded.graph.stage(stage.name)
                if spec.retry.can_retry(stage.attempt):
                    self._set_stage_state(loaded, stage.name, StageState.RETRYING)
                    self._emit(
                        run_id,
                        EventKind.RETRY_SCHEDULED,
                        ActorType.SYSTEM,
                        stage=stage.name,
                        attempt=stage.attempt,
                        reason="interrupted attempt found at resume",
                    )
                else:
                    self._set_stage_state(
                        loaded,
                        stage.name,
                        StageState.FAILED,
                        failure_kind=FailureKind.TRANSIENT.value,
                        error="interrupted; retries exhausted",
                    )
            self._emit(
                run_id,
                EventKind.RUN_RESUMED,
                ActorType.SYSTEM,
                target="run",
                result=run.state.value,
                reason="resume requested",
                data={"interrupted_stages": [s.name for s in interrupted]},
            )
            if run.state.is_waiting:
                self._gate_timed_out(loaded)
                self._save_run(loaded)
                return loaded.run
            if run.state is RunState.SUSPENDED or run.state is RunState.CREATED:
                self._set_run_state(loaded, RunState.RUNNING)
        return self.run(run_id)

    def stop(self, run_id: str, *, actor: str, reason: str) -> RunRecord:
        loaded = self._load(run_id)
        if loaded.run.state.is_terminal:
            return loaded.run
        with self._lock:
            self._safe_stop(
                loaded, f"OPERATOR_STOP: {reason}", actor=ActorType.HUMAN, data={"actor": actor}
            )
        return loaded.run

    def replan(
        self, run_id: str, *, trigger: str, data_updates: dict[str, Any] | None = None
    ) -> RunRecord:
        """Governed replanning on an explicit upstream change (FR-O14)."""
        loaded = self._load(run_id)
        if loaded.run.state.is_terminal:
            raise IllegalTransitionError("cannot replan a terminal run")
        with self._lock:
            previous = loaded.run.state
            if previous is not RunState.REPLANNING:
                self._set_run_state(loaded, RunState.REPLANNING)
            if data_updates:
                loaded.ctx.data.update(data_updates)
                loaded.ctx.requirement_version += 1
                loaded.run.requirement_version = loaded.ctx.requirement_version
            self._replan(loaded, trigger=trigger, from_stages=set())
            self._set_run_state(loaded, RunState.RUNNING)
            self._save_run(loaded)
        return loaded.run

    # --------------------------------------------------------------- inspection

    def load(self, run_id: str) -> RunRecord:
        return self._load(run_id).run

    def graph_view(self, run_id: str) -> dict[str, Any]:
        loaded = self._load(run_id)
        view = loaded.graph.to_dict()
        for stage in view["stages"]:
            rec = loaded.stages.get(stage["name"])
            if rec is not None:
                stage.update(
                    {
                        "state": rec.state.value,
                        "attempt": rec.attempt,
                        "started_at": rec.started_at.isoformat() if rec.started_at else None,
                        "ended_at": rec.ended_at.isoformat() if rec.ended_at else None,
                        "failure_kind": rec.failure_kind,
                        "fallback_used": rec.fallback_used,
                    }
                )
        view["run_state"] = loaded.run.state.value
        view["graph_version"] = loaded.run.graph_version
        view["open_gates"] = [
            name
            for name, rec in loaded.stages.items()
            if rec.state is StageState.READY and loaded.graph.stage(name).is_gate
        ]
        return view

    def open_gates(self, run_id: str) -> list[dict[str, Any]]:
        loaded = self._load(run_id)
        out: list[dict[str, Any]] = []
        for name, rec in loaded.stages.items():
            spec = loaded.graph.stage(name)
            if spec.is_gate and rec.state is StageState.READY:
                out.append(
                    {
                        "gate": name,
                        "kind": spec.gate_kind,
                        "opened_at": rec.started_at.isoformat() if rec.started_at else None,
                        "timeout_s": spec.gate.timeout_s,
                        "purpose": spec.purpose,
                        "options": ["approve", "reject"]
                        + (["clarify"] if spec.gate_kind == "clarification" else []),
                        "context": {
                            "requirement_version": loaded.ctx.requirement_version,
                            "upstream_outputs": {d: loaded.ctx.output(d) for d in spec.depends_on},
                            "decisions_so_far": loaded.ctx.decisions,
                        },
                    }
                )
        return out

    # ----------------------------------------------------------------- internals

    def _load(self, run_id: str) -> _Loaded:
        run = self._store.load_run(run_id)
        if run is None:
            raise WorkflowNotFoundError(f"workflow {run_id} not found")
        stages = self._store.load_stages(run_id)
        graph = self._build_graph(run.context)
        return _Loaded(run=run, stages=stages, graph=graph)

    def _build_graph(self, ctx: RunContext) -> WorkflowGraph:
        try:
            planner = self._planners[ctx.planner]
        except KeyError as exc:
            raise KeyError(f"no planner registered for {ctx.planner!r}") from exc
        return planner(ctx)

    def _persist_graph(self, run: RunRecord, graph: WorkflowGraph, *, version: int) -> None:
        groups = graph.parallel_groups()
        for spec in graph.stages():
            self._store.save_stage(
                StageRecord(
                    run_id=run.id,
                    name=spec.name,
                    owner=spec.owner,
                    state=StageState.PENDING,
                    parallel_group=groups.get(spec.name),
                )
            )
        self._store.save_edges(
            [EdgeRecord(run.id, version, e.from_stage, e.to_stage, e.kind) for e in graph.edges]
        )

    def _emit(
        self,
        run_id: str,
        kind: EventKind,
        actor: ActorType,
        *,
        stage: str | None = None,
        attempt: int | None = None,
        target: str | None = None,
        result: str | None = None,
        reason: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> AuditEvent:
        with self._lock:
            event = AuditEvent(
                run_id=run_id,
                seq=self._store.next_seq(run_id),
                kind=kind,
                actor_type=actor,
                at=self._clock(),
                stage=stage,
                attempt=attempt,
                target=target or (f"stage:{stage}" if stage else None),
                result=result,
                reason=reason,
                data=data or {},
            )
            self._store.append_event(event)
        return event

    def _save_run(self, loaded: _Loaded) -> None:
        loaded.run.updated_at = self._clock()
        loaded.run.graph_version = loaded.ctx.graph_version
        loaded.run.requirement_version = loaded.ctx.requirement_version
        self._store.save_run(loaded.run)

    def _set_run_state(
        self,
        loaded: _Loaded,
        new: RunState,
        *,
        event: EventKind | None = None,
        reason: str | None = None,
        terminal_reason: str | None = None,
    ) -> None:
        with self._lock:
            assert_run_transition(loaded.run.state, new)
            loaded.run.state = new
            if terminal_reason:
                loaded.run.terminal_reason = terminal_reason
            self._save_run(loaded)
            if event is not None:
                self._emit(
                    loaded.run.id,
                    event,
                    ActorType.SYSTEM,
                    target="run",
                    result=new.value,
                    reason=reason,
                )
            if new.is_terminal:
                self._snapshot_metrics(loaded)

    def _set_stage_state(
        self,
        loaded: _Loaded,
        name: str,
        new: StageState,
        *,
        failure_kind: str | None = None,
        error: str | None = None,
    ) -> StageRecord:
        with self._lock:
            rec = loaded.stages[name]
            assert_stage_transition(rec.state, new)
            rec.state = new
            if failure_kind is not None:
                rec.failure_kind = failure_kind
            if error is not None:
                rec.last_error = error
            self._store.save_stage(rec)
            return rec

    def _safe_stop(
        self,
        loaded: _Loaded,
        reason: str,
        *,
        actor: ActorType = ActorType.SYSTEM,
        data: dict[str, Any] | None = None,
    ) -> None:
        with self._lock:
            if loaded.run.state.is_terminal:
                return
            assert_run_transition(loaded.run.state, RunState.SAFE_STOPPED)
            loaded.run.state = RunState.SAFE_STOPPED
            loaded.run.terminal_reason = reason
            self._save_run(loaded)
            self._emit(
                loaded.run.id,
                EventKind.SAFE_STOP,
                actor,
                target="run",
                result=RunState.SAFE_STOPPED.value,
                reason=reason,
                data=data or {},
            )
            log.warning("safe_stop", reason=reason)
            self._snapshot_metrics(loaded)

    def _snapshot_metrics(self, loaded: _Loaded) -> None:
        metrics = compute_run_metrics(self._store.list_events(loaded.run.id))
        self._store.save_metrics(
            MetricsSnapshot(
                run_id=loaded.run.id,
                snapshot=metrics,
                e2e_latency_s=metrics["latency"]["end_to_end_s"],
                at=self._clock(),
            )
        )

    def _gate_timed_out(self, loaded: _Loaded) -> bool:
        if not loaded.run.state.is_waiting:
            return False
        now = self._clock()
        for name, rec in loaded.stages.items():
            spec = loaded.graph.stage(name)
            if spec.is_gate and rec.state is StageState.READY and spec.gate.timeout_s is not None:
                opened = rec.started_at or now
                if now - opened >= timedelta(seconds=spec.gate.timeout_s):
                    self._safe_stop(
                        loaded,
                        f"GATE_TIMEOUT: {name} received no decision within {spec.gate.timeout_s}s",
                        data={"gate": name},
                    )
                    return True
        return False

    # --- scheduling -----------------------------------------------------------

    def _tick(self, loaded: _Loaded) -> bool:
        """Execute one batch. Returns False when the run cannot progress further."""
        graph, states = loaded.graph, loaded.states()
        mapping = loaded.ctx.as_mapping()

        # 1. resolve conditions for ready stages (may skip several in a row)
        changed = True
        while changed:
            changed = False
            for name in graph.ready(states):
                if not graph.evaluate_condition(name, mapping):
                    self._set_stage_state(loaded, name, StageState.SKIPPED)
                    self._emit(
                        loaded.run.id,
                        EventKind.STAGE_SKIPPED,
                        ActorType.SYSTEM,
                        stage=name,
                        result=StageState.SKIPPED.value,
                        reason=(
                            f"condition '{graph.stage(name).condition_label or 'condition'}'"
                            " is false"
                        ),
                    )
                    states[name] = StageState.SKIPPED
                    changed = True

        ready = graph.ready(states)
        retrying = [
            n
            for n, st in states.items()
            if st is StageState.RETRYING
            and all(
                states.get(d, StageState.PENDING).satisfies_dependency
                for d in graph.stage(n).depends_on
            )
        ]
        agent_stages = [n for n in ready if not graph.stage(n).is_gate] + retrying
        gate_stages = [n for n in ready if graph.stage(n).is_gate]

        if agent_stages:
            outcomes = self._execute_batch(loaded, agent_stages)
            stops = [o for o in outcomes if o.safe_stop_reason]
            if stops:
                self._safe_stop(loaded, stops[0].safe_stop_reason or "SAFE_STOP")
                return False
            return True

        if gate_stages:
            self._open_gate(loaded, gate_stages[0])
            return False

        if all(st.satisfies_dependency or st is StageState.COMPENSATED for st in states.values()):
            self._set_run_state(
                loaded, RunState.COMPLETED, event=EventKind.RUN_COMPLETED, reason="all stages done"
            )
            return False

        self._safe_stop(loaded, "NO_PROGRESS: stages remain but none can start")
        return False

    def _open_gate(self, loaded: _Loaded, name: str) -> None:
        spec = loaded.graph.stage(name)
        with self._lock:
            rec = self._set_stage_state(loaded, name, StageState.READY)
            rec.started_at = self._clock()
            self._store.save_stage(rec)
            self._emit(
                loaded.run.id,
                EventKind.GATE_OPENED,
                ActorType.SYSTEM,
                stage=name,
                target=f"gate:{name}",
                result="WAITING",
                reason=spec.purpose or f"human decision required at {name}",
                data={
                    "gate_kind": spec.gate_kind,
                    "timeout_s": spec.gate.timeout_s,
                    "upstream_outputs": {d: loaded.ctx.output(d) for d in spec.depends_on},
                },
            )
            new_state = (
                RunState.WAITING_CLARIFICATION
                if spec.gate_kind == "clarification"
                else RunState.WAITING_APPROVAL
            )
            self._set_run_state(loaded, new_state)

    def _execute_batch(self, loaded: _Loaded, names: list[str]) -> list[_Outcome]:
        for name in names:
            if loaded.stages[name].state is StageState.PENDING:
                self._set_stage_state(loaded, name, StageState.READY)
                self._emit(
                    loaded.run.id,
                    EventKind.STAGE_READY,
                    ActorType.SYSTEM,
                    stage=name,
                    result="READY",
                )
        workers = max(1, min(self._max_workers, len(names)))
        pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="stage")
        try:
            futures = {name: pool.submit(self._run_stage, loaded, name) for name in names}
            return [futures[name].result() for name in names]
        finally:
            pool.shutdown(wait=True)

    # --- a single stage with its reliability policy ------------------------------

    def _run_stage(self, loaded: _Loaded, name: str) -> _Outcome:
        spec = loaded.graph.stage(name)
        run_id = loaded.run.id
        rec = loaded.stages[name]
        attempt = rec.attempt
        failed_before = rec.attempt > 0
        bind(run_id=run_id, stage=name)
        try:
            while True:
                attempt += 1
                delay = spec.retry.delay_for(attempt)
                if delay:
                    self._sleep(delay)
                self._start_attempt(loaded, name, attempt)
                try:
                    result = self._call_with_timeout(spec, loaded.ctx, name, attempt)
                except FutureTimeout:
                    kind, error = (
                        FailureKind.TRANSIENT,
                        f"attempt {attempt} exceeded {spec.timeout.seconds}s",
                    )
                    self._emit(
                        run_id,
                        EventKind.STAGE_TIMED_OUT,
                        ActorType.SYSTEM,
                        stage=name,
                        attempt=attempt,
                        result="TIMEOUT",
                        reason=error,
                    )
                except StageError as exc:
                    kind, error = exc.kind, exc.detail
                except (
                    Exception
                ) as exc:  # unexpected agent crash: permanent, never silently retried
                    kind, error = FailureKind.PERMANENT, f"{type(exc).__name__}: {exc}"
                else:
                    self._record_success(loaded, name, attempt, result, recovered=failed_before)
                    return _Outcome(name, StageState.SUCCEEDED)

                failed_before = True
                self._record_failure(loaded, name, attempt, kind, error)
                if kind is FailureKind.TRANSIENT and spec.retry.can_retry(attempt):
                    next_delay = spec.retry.delay_for(attempt + 1)
                    self._set_stage_state(loaded, name, StageState.RETRYING)
                    self._emit(
                        run_id,
                        EventKind.RETRY_SCHEDULED,
                        ActorType.SYSTEM,
                        stage=name,
                        attempt=attempt,
                        result="RETRYING",
                        reason=error,
                        data={
                            "next_attempt": attempt + 1,
                            "delay_s": next_delay,
                            "max_attempts": spec.retry.max_attempts,
                        },
                    )
                    self._emit(
                        run_id,
                        EventKind.RECOVERY_STARTED,
                        ActorType.SYSTEM,
                        stage=name,
                        attempt=attempt,
                        data={"mechanism": "retry"},
                    )
                    continue

                # exhausted or permanent
                rec = self._set_stage_state(
                    loaded, name, StageState.FAILED, failure_kind=kind.value, error=error
                )
                rec.ended_at = self._clock()
                with self._lock:
                    self._store.save_stage(rec)
                self._emit(
                    run_id,
                    EventKind.STAGE_FAILED,
                    ActorType.AGENT,
                    stage=name,
                    attempt=attempt,
                    result=StageState.FAILED.value,
                    reason=error,
                    data={
                        "failure_kind": kind.value,
                        "retry_eligible": kind is FailureKind.TRANSIENT,
                        "attempts": attempt,
                    },
                )
                if spec.fallback:
                    return self._run_fallback(loaded, spec, attempt, error)
                why = (
                    "failed permanently"
                    if kind is FailureKind.PERMANENT
                    else f"exhausted {spec.retry.max_attempts} attempts"
                )
                return _Outcome(
                    name, StageState.FAILED, f"RETRIES_EXHAUSTED: stage {name} {why} ({error})"
                )
        finally:
            unbind("run_id", "stage")

    def _run_fallback(self, loaded: _Loaded, spec: StageSpec, attempt: int, error: str) -> _Outcome:
        run_id, name = loaded.run.id, spec.name
        assert spec.fallback is not None
        self._emit(
            run_id,
            EventKind.RECOVERY_STARTED,
            ActorType.SYSTEM,
            stage=name,
            attempt=attempt,
            data={"mechanism": "fallback", "fallback_agent": spec.fallback},
        )
        try:
            result = self._agents.get(spec.fallback).execute(loaded.ctx, name, attempt)
        except Exception as exc:
            reason = (
                f"FALLBACK_FAILED: stage {name} fallback {spec.fallback!r} failed "
                f"({type(exc).__name__}: {exc})"
            )
            self._emit(
                run_id,
                EventKind.STAGE_FAILED,
                ActorType.AGENT,
                stage=name,
                attempt=attempt,
                result="FALLBACK_FAILED",
                reason=reason,
            )
            return _Outcome(name, StageState.FAILED, reason)
        result.output = {
            **result.output,
            "fallback": True,
            "fallback_agent": spec.fallback,
            "primary_error": error,
        }
        with self._lock:
            rec = self._set_stage_state(loaded, name, StageState.FALLBACK)
            rec.fallback_used = True
            rec.ended_at = self._clock()
            self._apply_result(loaded, name, attempt, result)
            self._emit(
                run_id,
                EventKind.FALLBACK_USED,
                ActorType.AGENT,
                stage=name,
                attempt=attempt,
                result=StageState.FALLBACK.value,
                reason=f"primary failed: {error}",
                data={"fallback_agent": spec.fallback},
            )
            self._emit(
                run_id,
                EventKind.RECOVERY_COMPLETED,
                ActorType.SYSTEM,
                stage=name,
                attempt=attempt,
                result="RECOVERED",
                data={"mechanism": "fallback"},
            )
        return _Outcome(name, StageState.FALLBACK)

    def _start_attempt(self, loaded: _Loaded, name: str, attempt: int) -> None:
        with self._lock:
            rec = loaded.stages[name]
            assert_stage_transition(rec.state, StageState.RUNNING)
            rec.state = StageState.RUNNING
            rec.attempt = attempt
            rec.started_at = self._clock()
            rec.ended_at = None
            self._store.save_stage(rec)
            self._emit(
                loaded.run.id,
                EventKind.STAGE_STARTED,
                ActorType.AGENT,
                stage=name,
                attempt=attempt,
                result=StageState.RUNNING.value,
                data={"agent": loaded.graph.stage(name).agent},
            )

    def _call_with_timeout(
        self, spec: StageSpec, ctx: RunContext, name: str, attempt: int
    ) -> StageResult:
        agent = self._agents.get(spec.agent)
        single = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"attempt-{name}")
        future = single.submit(agent.execute, ctx, name, attempt)
        try:
            return future.result(timeout=spec.timeout.seconds)
        finally:
            single.shutdown(wait=False)

    def _record_success(
        self, loaded: _Loaded, name: str, attempt: int, result: StageResult, *, recovered: bool
    ) -> None:
        with self._lock:
            rec = self._set_stage_state(loaded, name, StageState.SUCCEEDED)
            rec.ended_at = self._clock()
            self._apply_result(loaded, name, attempt, result)
            self._emit(
                loaded.run.id,
                EventKind.STAGE_SUCCEEDED,
                ActorType.AGENT,
                stage=name,
                attempt=attempt,
                result=StageState.SUCCEEDED.value,
                data={"artifacts": [k for k, _ in result.artifacts]},
            )
            if recovered:
                self._emit(
                    loaded.run.id,
                    EventKind.RECOVERY_COMPLETED,
                    ActorType.SYSTEM,
                    stage=name,
                    attempt=attempt,
                    result="RECOVERED",
                    data={"mechanism": "retry"},
                )

    def _record_failure(
        self, loaded: _Loaded, name: str, attempt: int, kind: FailureKind, error: str
    ) -> None:
        rec = loaded.stages[name]
        first = rec.failure_kind is None and attempt == 1
        with self._lock:
            rec.failure_kind = kind.value
            rec.last_error = error
            self._store.save_stage(rec)
            if first:
                self._emit(
                    loaded.run.id,
                    EventKind.FAILURE_DETECTED,
                    ActorType.SYSTEM,
                    stage=name,
                    attempt=attempt,
                    result=kind.value,
                    reason=error,
                )
        log.warning(
            "stage_attempt_failed", stage=name, attempt=attempt, kind=kind.value, error=error
        )

    def _apply_result(self, loaded: _Loaded, name: str, attempt: int, result: StageResult) -> None:
        """Persist outputs, artifacts (with lineage) and context updates. Caller holds the lock."""
        ctx, run_id = loaded.ctx, loaded.run.id
        spec = loaded.graph.stage(name)
        rec = loaded.stages[name]
        rec.output = result.output
        ctx.outputs[name] = result.output
        ctx.data.update(result.data_updates)
        ctx.assumptions.extend(result.assumptions)
        derived_from = sorted(
            {ref.id for kind, ref in ctx.artifacts.items() if ref.stage in spec.depends_on}
        )
        now = self._clock()
        for kind, content in result.artifacts:
            previous = ctx.artifacts.get(kind)
            version = previous.version + 1 if previous and previous.stage == name else 1
            artifact = ArtifactRecord(
                run_id=run_id,
                stage=name,
                kind=kind,
                version=version,
                content=content,
                derived_from=derived_from,
                policy_version=ctx.policy_version,
                created_at=now,
            )
            new_id = self._store.save_artifact(artifact)
            ctx.artifacts[kind] = ArtifactRef(id=new_id, kind=kind, version=version, stage=name)
        self._store.save_stage(rec)
        self._save_run(loaded)

    def _finish_stage(
        self,
        loaded: _Loaded,
        name: str,
        state: StageState,
        *,
        output: dict[str, Any] | None = None,
        failure_kind: str | None = None,
        error: str | None = None,
    ) -> None:
        if loaded.stages[name].state is StageState.READY:
            # a gate is "executed" by the human decision: READY -> RUNNING -> outcome
            self._set_stage_state(loaded, name, StageState.RUNNING)
        rec = self._set_stage_state(loaded, name, state, failure_kind=failure_kind, error=error)
        rec.ended_at = self._clock()
        if output is not None:
            rec.output = output
            loaded.ctx.outputs[name] = output
        self._store.save_stage(rec)

    # --- compensation (FR-O11) ---------------------------------------------------

    def _compensate(self, loaded: _Loaded, *, reason: str) -> list[str]:
        """Run compensating actions for side-effecting stages in reverse dependency order."""
        compensated: list[str] = []
        for name in reversed(loaded.graph.topological_order()):
            spec, rec = loaded.graph.stage(name), loaded.stages[name]
            if not spec.compensable or rec.state not in {StageState.SUCCEEDED, StageState.FALLBACK}:
                continue
            self._set_stage_state(loaded, name, StageState.COMPENSATING)
            self._emit(
                loaded.run.id,
                EventKind.COMPENSATION_STARTED,
                ActorType.SYSTEM,
                stage=name,
                reason=reason,
            )
            outcome = self._agents.get(spec.agent).compensate(loaded.ctx, name)
            self._set_stage_state(loaded, name, StageState.COMPENSATED)
            kind = (
                EventKind.ROLLBACK_COMPLETED
                if outcome.get("rollback")
                else EventKind.COMPENSATION_COMPLETED
            )
            self._emit(
                loaded.run.id,
                kind,
                ActorType.AGENT,
                stage=name,
                result=StageState.COMPENSATED.value,
                reason=reason,
                data=outcome,
            )
            compensated.append(name)
        return compensated

    # --- replanning (FR-O14, ADR-009) ---------------------------------------------

    def _replan(self, loaded: _Loaded, *, trigger: str, from_stages: set[str]) -> ReplanRecord:
        """Caller holds the lock and has put the run in REPLANNING."""
        run, ctx, old = loaded.run, loaded.ctx, loaded.graph
        before = old.to_dict()
        new = self._build_graph(ctx)
        diff = old.diff(new)
        touched = set(diff.touched)
        invalid: set[str] = set(touched)
        invalid |= old.downstream({n for n in touched if n in old.names()})
        invalid |= new.downstream({n for n in touched if n in new.names()})
        invalid |= new.downstream(from_stages)
        invalid -= {n for n in from_stages}  # the gate itself keeps its decision
        invalid &= set(new.names()) | set(old.names())

        reset: list[str] = []
        for name in sorted(
            invalid, key=lambda n: old.topological_order().index(n) if n in old.names() else 10_000
        ):
            rec = loaded.stages.get(name)
            if name in diff.removed:
                self._store.delete_stages(run.id, [name])
                loaded.stages.pop(name, None)
                continue
            if rec is None:  # added stage
                groups = new.parallel_groups()
                rec = StageRecord(
                    run_id=run.id,
                    name=name,
                    owner=new.stage(name).owner,
                    state=StageState.PENDING,
                    parallel_group=groups.get(name),
                )
                loaded.stages[name] = rec
                self._store.save_stage(rec)
                reset.append(name)
                continue
            if rec.state is not StageState.PENDING:
                if rec.state is StageState.COMPENSATING:
                    continue
                assert_stage_transition(rec.state, StageState.INVALIDATED)
                rec.state = StageState.INVALIDATED
                self._store.save_stage(rec)
                self._emit(
                    run.id,
                    EventKind.ARTIFACT_INVALIDATED,
                    ActorType.SYSTEM,
                    stage=name,
                    result=StageState.INVALIDATED.value,
                    reason=trigger,
                )
            rec.state = StageState.PENDING
            rec.attempt = 0
            rec.started_at = rec.ended_at = None
            rec.failure_kind = rec.last_error = None
            rec.fallback_used = False
            rec.output = None
            self._store.save_stage(rec)
            ctx.outputs.pop(name, None)
            for kind in [k for k, ref in ctx.artifacts.items() if ref.stage == name]:
                ctx.artifacts.pop(kind)
            reset.append(name)
        invalidated_ids = self._store.invalidate_artifacts(
            run.id, [n for n in invalid if n not in diff.removed]
        )

        ctx.graph_version += 1
        run.graph_version = ctx.graph_version
        self._store.save_edges(
            [
                EdgeRecord(run.id, ctx.graph_version, e.from_stage, e.to_stage, e.kind)
                for e in new.edges
            ]
        )
        loaded.graph = new
        record = ReplanRecord(
            run_id=run.id,
            trigger=trigger,
            graph_before=before,
            graph_after=new.to_dict(),
            invalidated=sorted(invalid),
            at=self._clock(),
        )
        self._store.save_replan(record)
        self._emit(
            run.id,
            EventKind.REPLAN,
            ActorType.SYSTEM,
            target="graph",
            result=f"v{ctx.graph_version}",
            reason=trigger,
            data={
                "diff": diff.to_dict(),
                "invalidated_stages": sorted(invalid),
                "invalidated_artifacts": invalidated_ids,
                "reset": reset,
                "requirement_version": ctx.requirement_version,
                "graph_version": ctx.graph_version,
            },
        )
        self._save_run(loaded)
        log.info(
            "replan", trigger=trigger, invalidated=sorted(invalid), graph_version=ctx.graph_version
        )
        return record
