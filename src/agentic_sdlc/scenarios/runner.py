"""Scenario runner: drives a scenario through the real engine, one step at a time.

The runner never decides anything itself. Each ``Decide`` step is executed
through ``Engine.decide`` with the actor the operator supplied; with
``decide=False`` the runner stops at the first open gate and reports the exact
CLI command a human would run.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from agentic_sdlc.config import Settings
from agentic_sdlc.orchestration.engine import Engine
from agentic_sdlc.orchestration.release import compute_release_decision
from agentic_sdlc.orchestration.store import WorkflowStore
from agentic_sdlc.policy.registry import POLICIES
from agentic_sdlc.scenarios import Decide, Restart, Run, Scenario, Wait

EngineFactory = Callable[[Settings], Engine]


@dataclass
class ScenarioOutcome:
    scenario: str
    run_id: str
    state: str
    terminal_reason: str | None
    release_decision: str
    steps: list[dict[str, Any]] = field(default_factory=list)
    stopped_at_gate: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "run_id": self.run_id,
            "state": self.state,
            "terminal_reason": self.terminal_reason,
            "release_decision": self.release_decision,
            "steps": self.steps,
            "stopped_at_gate": self.stopped_at_gate,
        }


def scenario_settings(base: Settings, scenario: Scenario) -> Settings:
    return Settings(**{**base.model_dump(), **scenario.settings})


def release_for(store: WorkflowStore, run_id: str) -> dict[str, Any]:
    run = store.load_run(run_id)
    if run is None:
        raise KeyError(run_id)
    return compute_release_decision(
        run_state=run.state,
        stage_states={n: s.state for n, s in store.load_stages(run_id).items()},
        evaluations=store.list_policy_evaluations(run_id),
        exceptions=store.list_policy_exceptions(run_id),
        mandatory={p.id: p.mandatory for p in POLICIES},
    )


def run_scenario(
    scenario: Scenario,
    *,
    store: WorkflowStore,
    engine_factory: EngineFactory,
    base_settings: Settings,
    actor: str,
    decide: bool = True,
    sleep: Callable[[float], None] = time.sleep,
) -> ScenarioOutcome:
    settings = scenario_settings(base_settings, scenario)
    engine = engine_factory(settings)
    run_id = engine.start(
        title=scenario.title, requirement=scenario.requirement, scope=scenario.scope
    )
    log: list[dict[str, Any]] = []
    stopped: dict[str, Any] | None = None
    for step in scenario.steps:
        if isinstance(step, Run):
            run = engine.run(run_id, max_batches=step.max_batches)
            log.append({"step": "run", "max_batches": step.max_batches, "state": run.state.value})
        elif isinstance(step, Restart):
            engine = engine_factory(settings)  # fresh engine over the same store
            run = engine.resume(run_id)
            log.append({"step": "restart+resume", "state": run.state.value})
        elif isinstance(step, Wait):
            sleep(step.seconds)
            log.append({"step": "wait", "seconds": step.seconds})
        elif isinstance(step, Decide):
            gates = {g["gate"]: g for g in engine.open_gates(run_id)}
            if step.gate not in gates:
                log.append({"step": "decide", "gate": step.gate, "skipped": "gate not open"})
                continue
            payload = step.resolve(gates[step.gate])
            if not decide:
                stopped = {
                    "gate": step.gate,
                    "scripted_decision": step.decision,
                    "scripted_reason": step.reason,
                    "scripted_payload": payload,
                    "command": (
                        f"agentic-sdlc workflow decide {run_id} {step.gate} {step.decision} "
                        f"--actor <you> --reason '{step.reason}' --payload '{_json(payload)}'"
                    ),
                }
                break
            engine.decide(
                run_id,
                gate=step.gate,
                actor=actor,
                decision=step.decision,
                reason=step.reason,
                payload=payload,
            )
            log.append(
                {
                    "step": "decide",
                    "gate": step.gate,
                    "decision": step.decision,
                    "actor": actor,
                    "payload": payload,
                }
            )
    final = engine.load(run_id)
    return ScenarioOutcome(
        scenario=scenario.name,
        run_id=run_id,
        state=final.state.value,
        terminal_reason=final.terminal_reason,
        release_decision=release_for(store, run_id)["decision"],
        steps=log,
        stopped_at_gate=stopped,
    )


def _json(data: dict[str, Any]) -> str:
    import json

    return json.dumps(data, separators=(",", ":"))
