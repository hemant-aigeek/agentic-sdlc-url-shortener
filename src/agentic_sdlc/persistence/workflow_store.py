"""SQLite implementation of ``WorkflowStore`` (ADR-003, ADR-006)."""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.engine import CursorResult, Row

from agentic_sdlc.orchestration.context import RunContext
from agentic_sdlc.orchestration.events import ActorType, AuditEvent, EventKind
from agentic_sdlc.orchestration.states import RunState, StageState
from agentic_sdlc.orchestration.store import (
    ArtifactRecord,
    DecisionRecord,
    EdgeRecord,
    MetricsSnapshot,
    PolicyEvaluationRecord,
    PolicyExceptionRecord,
    ReplanRecord,
    RunRecord,
    StageRecord,
    WorkflowStore,
)
from agentic_sdlc.persistence.db import Database
from agentic_sdlc.persistence.tables import (
    policy_evaluations,
    policy_exceptions,
    replan_events,
    run_metrics,
    workflow_artifacts,
    workflow_decisions,
    workflow_edges,
    workflow_events,
    workflow_runs,
    workflow_stages,
)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _m(row: Row[Any]) -> dict[str, Any]:
    return dict(row._mapping)


def _pk(result: CursorResult[Any]) -> int:
    pk = result.inserted_primary_key
    assert pk is not None
    return int(pk[0])


class SqlWorkflowStore(WorkflowStore):
    def __init__(self, db: Database) -> None:
        self._db = db
        self._seq_lock = threading.Lock()

    # --- runs ----------------------------------------------------------------

    def create_run(self, run: RunRecord) -> None:
        with self._db.begin() as conn:
            conn.execute(insert(workflow_runs).values(**self._run_values(run)))

    def save_run(self, run: RunRecord) -> None:
        values = self._run_values(run)
        values.pop("id")
        with self._db.begin() as conn:
            conn.execute(update(workflow_runs).where(workflow_runs.c.id == run.id).values(**values))

    @staticmethod
    def _run_values(run: RunRecord) -> dict[str, Any]:
        return {
            "id": run.id,
            "title": run.title,
            "scope": run.scope,
            "state": run.state.value,
            "requirement_raw": run.requirement_raw,
            "requirement_version": run.requirement_version,
            "policy_version": run.policy_version,
            "graph_version": run.graph_version,
            "context": run.context.to_dict(),
            "created_at": run.created_at,
            "updated_at": run.updated_at,
            "terminal_reason": run.terminal_reason,
        }

    def load_run(self, run_id: str) -> RunRecord | None:
        with self._db.connect() as conn:
            row = conn.execute(select(workflow_runs).where(workflow_runs.c.id == run_id)).first()
        return self._row_to_run(row) if row is not None else None

    def list_runs(self) -> list[RunRecord]:
        with self._db.connect() as conn:
            rows = conn.execute(select(workflow_runs).order_by(workflow_runs.c.created_at)).all()
        return [self._row_to_run(r) for r in rows]

    @staticmethod
    def _row_to_run(row: Row[Any]) -> RunRecord:
        m = _m(row)
        created = _aware(m["created_at"])
        updated = _aware(m["updated_at"])
        assert created is not None and updated is not None
        return RunRecord(
            id=m["id"],
            title=m["title"],
            scope=m["scope"],
            state=RunState(m["state"]),
            requirement_raw=m["requirement_raw"],
            requirement_version=m["requirement_version"],
            policy_version=m["policy_version"],
            graph_version=m["graph_version"],
            context=RunContext.from_dict(m["context"]),
            created_at=created,
            updated_at=updated,
            terminal_reason=m["terminal_reason"],
        )

    # --- stages & edges -------------------------------------------------------

    def save_stage(self, stage: StageRecord) -> None:
        values = {
            "owner": stage.owner,
            "state": stage.state.value,
            "attempt": stage.attempt,
            "parallel_group": stage.parallel_group,
            "started_at": stage.started_at,
            "ended_at": stage.ended_at,
            "failure_kind": stage.failure_kind,
            "fallback_used": stage.fallback_used,
            "last_error": stage.last_error,
            "output": stage.output,
        }
        with self._db.begin() as conn:
            exists = conn.execute(
                select(workflow_stages.c.name).where(
                    workflow_stages.c.run_id == stage.run_id,
                    workflow_stages.c.name == stage.name,
                )
            ).first()
            if exists:
                conn.execute(
                    update(workflow_stages)
                    .where(
                        workflow_stages.c.run_id == stage.run_id,
                        workflow_stages.c.name == stage.name,
                    )
                    .values(**values)
                )
            else:
                conn.execute(
                    insert(workflow_stages).values(run_id=stage.run_id, name=stage.name, **values)
                )

    def load_stages(self, run_id: str) -> dict[str, StageRecord]:
        with self._db.connect() as conn:
            rows = conn.execute(
                select(workflow_stages).where(workflow_stages.c.run_id == run_id)
            ).all()
        out: dict[str, StageRecord] = {}
        for row in rows:
            m = _m(row)
            out[m["name"]] = StageRecord(
                run_id=m["run_id"],
                name=m["name"],
                owner=m["owner"],
                state=StageState(m["state"]),
                attempt=m["attempt"],
                parallel_group=m["parallel_group"],
                started_at=_aware(m["started_at"]),
                ended_at=_aware(m["ended_at"]),
                failure_kind=m["failure_kind"],
                fallback_used=bool(m["fallback_used"]),
                last_error=m["last_error"],
                output=m["output"],
            )
        return out

    def delete_stages(self, run_id: str, names: list[str]) -> None:
        if not names:
            return
        with self._db.begin() as conn:
            conn.execute(
                delete(workflow_stages).where(
                    workflow_stages.c.run_id == run_id, workflow_stages.c.name.in_(names)
                )
            )

    def save_edges(self, edges: list[EdgeRecord]) -> None:
        if not edges:
            return
        with self._db.begin() as conn:
            conn.execute(
                insert(workflow_edges),
                [
                    {
                        "run_id": e.run_id,
                        "graph_version": e.graph_version,
                        "from_stage": e.from_stage,
                        "to_stage": e.to_stage,
                        "kind": e.kind,
                    }
                    for e in edges
                ],
            )

    def load_edges(self, run_id: str, graph_version: int) -> list[EdgeRecord]:
        with self._db.connect() as conn:
            rows = conn.execute(
                select(workflow_edges).where(
                    workflow_edges.c.run_id == run_id,
                    workflow_edges.c.graph_version == graph_version,
                )
            ).all()
        return [
            EdgeRecord(
                run_id=_m(r)["run_id"],
                graph_version=_m(r)["graph_version"],
                from_stage=_m(r)["from_stage"],
                to_stage=_m(r)["to_stage"],
                kind=_m(r)["kind"],
            )
            for r in rows
        ]

    # --- events (append-only) ------------------------------------------------

    def next_seq(self, run_id: str) -> int:
        with self._db.connect() as conn:
            current = conn.execute(
                select(func.max(workflow_events.c.seq)).where(workflow_events.c.run_id == run_id)
            ).scalar()
        return int(current or 0) + 1

    def append_event(self, event: AuditEvent) -> None:
        with self._seq_lock, self._db.begin() as conn:
            conn.execute(
                insert(workflow_events).values(
                    run_id=event.run_id,
                    seq=event.seq,
                    kind=event.kind.value,
                    actor_type=event.actor_type.value,
                    stage=event.stage,
                    attempt=event.attempt,
                    target=event.target,
                    result=event.result,
                    reason=event.reason,
                    data=event.data,
                    at=event.at,
                )
            )

    def list_events(self, run_id: str) -> list[AuditEvent]:
        with self._db.connect() as conn:
            rows = conn.execute(
                select(workflow_events)
                .where(workflow_events.c.run_id == run_id)
                .order_by(workflow_events.c.seq)
            ).all()
        out: list[AuditEvent] = []
        for row in rows:
            m = _m(row)
            at = _aware(m["at"])
            assert at is not None
            out.append(
                AuditEvent(
                    run_id=m["run_id"],
                    seq=m["seq"],
                    kind=EventKind(m["kind"]),
                    actor_type=ActorType(m["actor_type"]),
                    at=at,
                    stage=m["stage"],
                    attempt=m["attempt"],
                    target=m["target"],
                    result=m["result"],
                    reason=m["reason"],
                    data=m["data"] or {},
                )
            )
        return out

    # --- artifacts --------------------------------------------------------------

    def save_artifact(self, artifact: ArtifactRecord) -> int:
        with self._db.begin() as conn:
            result = conn.execute(
                insert(workflow_artifacts).values(
                    run_id=artifact.run_id,
                    stage=artifact.stage,
                    kind=artifact.kind,
                    version=artifact.version,
                    content=artifact.content,
                    derived_from=artifact.derived_from,
                    policy_version=artifact.policy_version,
                    invalidated=artifact.invalidated,
                    created_at=artifact.created_at,
                )
            )
            new_id = _pk(result)
        artifact.id = new_id
        return artifact.id

    def list_artifacts(self, run_id: str, include_invalidated: bool = True) -> list[ArtifactRecord]:
        stmt = select(workflow_artifacts).where(workflow_artifacts.c.run_id == run_id)
        if not include_invalidated:
            stmt = stmt.where(workflow_artifacts.c.invalidated.is_(False))
        with self._db.connect() as conn:
            rows = conn.execute(stmt.order_by(workflow_artifacts.c.id)).all()
        out: list[ArtifactRecord] = []
        for row in rows:
            m = _m(row)
            created = _aware(m["created_at"])
            assert created is not None
            out.append(
                ArtifactRecord(
                    id=m["id"],
                    run_id=m["run_id"],
                    stage=m["stage"],
                    kind=m["kind"],
                    version=m["version"],
                    content=m["content"],
                    derived_from=list(m["derived_from"] or []),
                    policy_version=m["policy_version"],
                    invalidated=bool(m["invalidated"]),
                    created_at=created,
                )
            )
        return out

    def invalidate_artifacts(self, run_id: str, stages: list[str]) -> list[int]:
        if not stages:
            return []
        with self._db.begin() as conn:
            ids = [
                int(r[0])
                for r in conn.execute(
                    select(workflow_artifacts.c.id).where(
                        workflow_artifacts.c.run_id == run_id,
                        workflow_artifacts.c.stage.in_(stages),
                        workflow_artifacts.c.invalidated.is_(False),
                    )
                ).all()
            ]
            if ids:
                conn.execute(
                    update(workflow_artifacts)
                    .where(workflow_artifacts.c.id.in_(ids))
                    .values(invalidated=True)
                )
        return ids

    # --- decisions --------------------------------------------------------------

    def save_decision(self, decision: DecisionRecord) -> int:
        with self._db.begin() as conn:
            result = conn.execute(
                insert(workflow_decisions).values(
                    run_id=decision.run_id,
                    gate=decision.gate,
                    actor=decision.actor,
                    decision=decision.decision,
                    reason=decision.reason,
                    payload=decision.payload,
                    artifact_version=decision.artifact_version,
                    decided_at=decision.decided_at,
                )
            )
            decision.id = _pk(result)
        return decision.id

    def list_decisions(self, run_id: str) -> list[DecisionRecord]:
        with self._db.connect() as conn:
            rows = conn.execute(
                select(workflow_decisions)
                .where(workflow_decisions.c.run_id == run_id)
                .order_by(workflow_decisions.c.id)
            ).all()
        out: list[DecisionRecord] = []
        for row in rows:
            m = _m(row)
            at = _aware(m["decided_at"])
            assert at is not None
            out.append(
                DecisionRecord(
                    id=m["id"],
                    run_id=m["run_id"],
                    gate=m["gate"],
                    actor=m["actor"],
                    decision=m["decision"],
                    reason=m["reason"],
                    payload=m["payload"] or {},
                    artifact_version=m["artifact_version"],
                    decided_at=at,
                )
            )
        return out

    # --- replanning, policy, metrics ------------------------------------------

    def save_replan(self, replan: ReplanRecord) -> int:
        with self._db.begin() as conn:
            result = conn.execute(
                insert(replan_events).values(
                    run_id=replan.run_id,
                    trigger=replan.trigger,
                    graph_before=replan.graph_before,
                    graph_after=replan.graph_after,
                    invalidated=replan.invalidated,
                    at=replan.at,
                )
            )
            replan.id = _pk(result)
        return replan.id

    def list_replans(self, run_id: str) -> list[ReplanRecord]:
        with self._db.connect() as conn:
            rows = conn.execute(
                select(replan_events)
                .where(replan_events.c.run_id == run_id)
                .order_by(replan_events.c.id)
            ).all()
        out: list[ReplanRecord] = []
        for row in rows:
            m = _m(row)
            at = _aware(m["at"])
            assert at is not None
            out.append(
                ReplanRecord(
                    id=m["id"],
                    run_id=m["run_id"],
                    trigger=m["trigger"],
                    graph_before=m["graph_before"],
                    graph_after=m["graph_after"],
                    invalidated=list(m["invalidated"]),
                    at=at,
                )
            )
        return out

    def save_policy_evaluation(self, evaluation: PolicyEvaluationRecord) -> int:
        with self._db.begin() as conn:
            result = conn.execute(
                insert(policy_evaluations).values(
                    run_id=evaluation.run_id,
                    stage=evaluation.stage,
                    policy_id=evaluation.policy_id,
                    policy_version=evaluation.policy_version,
                    outcome=evaluation.outcome,
                    detail=evaluation.detail,
                    at=evaluation.at,
                )
            )
            evaluation.id = _pk(result)
        return evaluation.id

    def list_policy_evaluations(self, run_id: str) -> list[PolicyEvaluationRecord]:
        with self._db.connect() as conn:
            rows = conn.execute(
                select(policy_evaluations)
                .where(policy_evaluations.c.run_id == run_id)
                .order_by(policy_evaluations.c.id)
            ).all()
        out: list[PolicyEvaluationRecord] = []
        for row in rows:
            m = _m(row)
            at = _aware(m["at"])
            assert at is not None
            out.append(
                PolicyEvaluationRecord(
                    id=m["id"],
                    run_id=m["run_id"],
                    stage=m["stage"],
                    policy_id=m["policy_id"],
                    policy_version=m["policy_version"],
                    outcome=m["outcome"],
                    detail=m["detail"],
                    at=at,
                )
            )
        return out

    def save_policy_exception(self, exc: PolicyExceptionRecord) -> int:
        values = {
            "run_id": exc.run_id,
            "policy_id": exc.policy_id,
            "scope": exc.scope,
            "reason": exc.reason,
            "approver": exc.approver,
            "compensating_control": exc.compensating_control,
            "approved_at": exc.approved_at,
            "expires_at": exc.expires_at,
            "status": exc.status,
        }
        with self._db.begin() as conn:
            if exc.id is None:
                result = conn.execute(insert(policy_exceptions).values(**values))
                exc.id = _pk(result)
            else:
                conn.execute(
                    update(policy_exceptions)
                    .where(policy_exceptions.c.id == exc.id)
                    .values(**values)
                )
        return exc.id

    def list_policy_exceptions(self, run_id: str) -> list[PolicyExceptionRecord]:
        with self._db.connect() as conn:
            rows = conn.execute(
                select(policy_exceptions)
                .where(policy_exceptions.c.run_id == run_id)
                .order_by(policy_exceptions.c.id)
            ).all()
        out: list[PolicyExceptionRecord] = []
        for row in rows:
            m = _m(row)
            approved = _aware(m["approved_at"])
            assert approved is not None
            out.append(
                PolicyExceptionRecord(
                    id=m["id"],
                    run_id=m["run_id"],
                    policy_id=m["policy_id"],
                    scope=m["scope"],
                    reason=m["reason"],
                    approver=m["approver"],
                    compensating_control=m["compensating_control"],
                    approved_at=approved,
                    expires_at=_aware(m["expires_at"]),
                    status=m["status"],
                )
            )
        return out

    def save_metrics(self, metrics: MetricsSnapshot) -> None:
        at = metrics.at or datetime.now(UTC)
        with self._db.begin() as conn:
            exists = conn.execute(
                select(run_metrics.c.run_id).where(run_metrics.c.run_id == metrics.run_id)
            ).first()
            values = {
                "snapshot": metrics.snapshot,
                "e2e_latency_s": metrics.e2e_latency_s,
                "at": at,
            }
            if exists:
                conn.execute(
                    update(run_metrics)
                    .where(run_metrics.c.run_id == metrics.run_id)
                    .values(**values)
                )
            else:
                conn.execute(insert(run_metrics).values(run_id=metrics.run_id, **values))

    def load_metrics(self, run_id: str) -> MetricsSnapshot | None:
        with self._db.connect() as conn:
            row = conn.execute(select(run_metrics).where(run_metrics.c.run_id == run_id)).first()
        if row is None:
            return None
        m = _m(row)
        return MetricsSnapshot(
            run_id=m["run_id"],
            snapshot=m["snapshot"],
            e2e_latency_s=m["e2e_latency_s"],
            at=_aware(m["at"]),
        )
