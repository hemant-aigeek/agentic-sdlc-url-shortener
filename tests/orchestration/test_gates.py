"""FR-G01..G05, NFR-11 / ADR-007: human gates are enforced by the engine, not by convention."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from agentic_sdlc.config import Settings
from agentic_sdlc.errors import GateRequiredError
from agentic_sdlc.orchestration.context import RunContext
from agentic_sdlc.orchestration.events import EventKind
from agentic_sdlc.orchestration.graph import WorkflowGraph
from agentic_sdlc.orchestration.policies import GatePolicy
from agentic_sdlc.orchestration.states import RunState, StageState
from agentic_sdlc.orchestration.store import WorkflowStore
from tests.orchestration.conftest import ScriptedAgent, make_engine, stage

pytestmark = pytest.mark.orchestration


def gated(_: RunContext) -> WorkflowGraph:
    #  a ─► approve[HUMAN] ─► b ─► c
    #  a is compensable (has side effects), b is compensable too
    return WorkflowGraph.build(
        [
            stage("a", compensable=True),
            stage("approve", "a", owner="human", purpose="design approval"),
            stage("b", "approve", compensable=True),
            stage("c", "b"),
        ]
    )


def gated_with_timeout(_: RunContext) -> WorkflowGraph:
    return WorkflowGraph.build(
        [
            stage("a"),
            stage("approve", "a", owner="human", gate=GatePolicy(timeout_s=60)),
            stage("b", "approve"),
        ]
    )


class FakeClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


@pytest.mark.req("FR-G01", "NFR-11")
def test_run_stops_at_gate_and_does_not_execute_downstream(
    store: WorkflowStore, agent: ScriptedAgent, settings: Settings
) -> None:
    engine = make_engine(store, agent, settings, {"g": gated})
    run_id = engine.start(title="t", requirement="r", scope="greenfield", planner="g")
    run = engine.run(run_id)
    assert run.state is RunState.WAITING_APPROVAL
    assert [c.stage for c in agent.calls] == ["a"]
    stages = store.load_stages(run_id)
    assert stages["approve"].state is StageState.READY and stages["b"].state is StageState.PENDING
    assert engine.open_gates(run_id)[0]["gate"] == "approve"
    assert engine.open_gates(run_id)[0]["context"]["upstream_outputs"]["a"]["done"] == "a"


@pytest.mark.req("FR-G04", "NFR-11")
def test_running_again_without_a_decision_does_not_advance(
    store: WorkflowStore, agent: ScriptedAgent, settings: Settings
) -> None:
    engine = make_engine(store, agent, settings, {"g": gated})
    run_id = engine.start(title="t", requirement="r", scope="greenfield", planner="g")
    engine.run(run_id)
    for _ in range(3):
        assert engine.run(run_id).state is RunState.WAITING_APPROVAL
        assert engine.resume(run_id).state is RunState.WAITING_APPROVAL
    assert [c.stage for c in agent.calls] == ["a"]


@pytest.mark.req("FR-G02", "FR-G03")
def test_approve_records_attributable_decision_and_continues(
    store: WorkflowStore, agent: ScriptedAgent, settings: Settings
) -> None:
    engine = make_engine(store, agent, settings, {"g": gated})
    run_id = engine.start(title="t", requirement="r", scope="greenfield", planner="g")
    engine.run(run_id)
    run = engine.decide(
        run_id,
        gate="approve",
        actor="hemant",
        decision="approve",
        reason="design is sound",
        payload={"api_change_acknowledged": True},
    )
    assert run.state is RunState.RUNNING
    run = engine.run(run_id)
    assert run.state is RunState.COMPLETED
    assert [c.stage for c in agent.calls] == ["a", "b", "c"]
    decision = store.list_decisions(run_id)[0]
    assert (decision.actor, decision.decision, decision.reason, decision.gate) == (
        "hemant",
        "approve",
        "design is sound",
        "approve",
    )
    assert decision.payload == {"api_change_acknowledged": True} and decision.decided_at is not None
    event = next(e for e in store.list_events(run_id) if e.kind is EventKind.DECISION_RECORDED)
    assert (
        event.actor_type.value == "human"
        and event.result == "approve"
        and event.data["actor"] == "hemant"
    )
    assert run.context.decisions[0]["gate"] == "approve"


@pytest.mark.req("FR-G05", "FR-O11")
def test_reject_stops_downstream_and_compensates_in_reverse_order(
    store: WorkflowStore, agent: ScriptedAgent, settings: Settings
) -> None:
    engine = make_engine(store, agent, settings, {"g": gated})
    run_id = engine.start(title="t", requirement="r", scope="greenfield", planner="g")
    engine.run(run_id)
    run = engine.decide(
        run_id, gate="approve", actor="hemant", decision="reject", reason="design violates boundary"
    )
    assert run.state is RunState.REJECTED
    assert run.terminal_reason is not None and "design violates boundary" in run.terminal_reason
    assert [c.stage for c in agent.calls] == ["a"]  # b, c never ran
    assert agent.compensations == ["a"]  # the only side-effecting completed stage
    stages = store.load_stages(run_id)
    assert stages["a"].state is StageState.COMPENSATED and stages["b"].state is StageState.PENDING
    kinds = [e.kind for e in store.list_events(run_id)]
    assert (
        kinds.index(EventKind.COMPENSATION_STARTED)
        < kinds.index(EventKind.COMPENSATION_COMPLETED)
        < kinds.index(EventKind.RUN_REJECTED)
    )
    assert engine.run(run_id).state is RunState.REJECTED  # terminal stays terminal


@pytest.mark.req("FR-G05", "FR-O11")
def test_reject_after_more_progress_compensates_reverse_dependency_order(
    store: WorkflowStore, agent: ScriptedAgent, settings: Settings
) -> None:
    def two_gates(_: RunContext) -> WorkflowGraph:
        return WorkflowGraph.build(
            [
                stage("a", compensable=True),
                stage("g1", "a", owner="human"),
                stage("b", "g1", compensable=True),
                stage("g2", "b", owner="human"),
            ]
        )

    engine = make_engine(store, agent, settings, {"g": two_gates})
    run_id = engine.start(title="t", requirement="r", scope="greenfield", planner="g")
    engine.run(run_id)
    engine.decide(run_id, gate="g1", actor="h", decision="approve", reason="ok")
    engine.run(run_id)
    engine.decide(run_id, gate="g2", actor="h", decision="reject", reason="no")
    assert agent.compensations == ["b", "a"]


@pytest.mark.req("FR-G04")
def test_gate_timeout_safe_stops_instead_of_advancing(
    store: WorkflowStore, agent: ScriptedAgent, settings: Settings
) -> None:
    clock = FakeClock()
    engine = make_engine(store, agent, settings, {"g": gated_with_timeout}, clock=clock)
    run_id = engine.start(title="t", requirement="r", scope="greenfield", planner="g")
    assert engine.run(run_id).state is RunState.WAITING_APPROVAL
    clock.advance(59)
    assert engine.resume(run_id).state is RunState.WAITING_APPROVAL
    clock.advance(2)
    run = engine.resume(run_id)
    assert run.state is RunState.SAFE_STOPPED
    assert run.terminal_reason is not None and run.terminal_reason.startswith("GATE_TIMEOUT")
    assert [c.stage for c in agent.calls] == ["a"]
    with pytest.raises(GateRequiredError):
        engine.decide(run_id, gate="approve", actor="h", decision="approve", reason="late")


@pytest.mark.req("FR-G01", "NFR-11")
def test_decision_on_closed_or_unknown_gate_is_refused(
    store: WorkflowStore, agent: ScriptedAgent, settings: Settings
) -> None:
    engine = make_engine(store, agent, settings, {"g": gated})
    run_id = engine.start(title="t", requirement="r", scope="greenfield", planner="g")
    with pytest.raises(GateRequiredError):
        engine.decide(run_id, gate="approve", actor="h", decision="approve", reason="too early")
    engine.run(run_id)
    with pytest.raises(GateRequiredError):
        engine.decide(run_id, gate="b", actor="h", decision="approve", reason="not a gate")
    with pytest.raises(GateRequiredError):
        engine.decide(run_id, gate="approve", actor="h", decision="clarify", reason="wrong kind")
    with pytest.raises(GateRequiredError):
        engine.decide(run_id, gate="approve", actor="h", decision="maybe", reason="not a decision")


@pytest.mark.req("NFR-11")
def test_forged_stage_row_cannot_move_a_waiting_run(
    store: WorkflowStore, agent: ScriptedAgent, settings: Settings
) -> None:
    """The run state, not the stage row, gates progress: a forged gate row changes nothing."""
    engine = make_engine(store, agent, settings, {"g": gated})
    run_id = engine.start(title="t", requirement="r", scope="greenfield", planner="g")
    engine.run(run_id)
    forged = store.load_stages(run_id)["approve"]
    forged.state = StageState.SUCCEEDED
    store.save_stage(forged)
    assert engine.run(run_id).state is RunState.WAITING_APPROVAL
    assert engine.resume(run_id).state is RunState.WAITING_APPROVAL
    assert [c.stage for c in agent.calls] == ["a"]
    assert not store.list_decisions(run_id)


@pytest.mark.req("FR-G01")
def test_operator_stop_is_recorded_safe_stop(
    store: WorkflowStore, agent: ScriptedAgent, settings: Settings
) -> None:
    engine = make_engine(store, agent, settings, {"g": gated})
    run_id = engine.start(title="t", requirement="r", scope="greenfield", planner="g")
    engine.run(run_id)
    run = engine.stop(run_id, actor="hemant", reason="halting for review")
    assert (
        run.state is RunState.SAFE_STOPPED
        and run.terminal_reason == "OPERATOR_STOP: halting for review"
    )
    ev = next(e for e in store.list_events(run_id) if e.kind is EventKind.SAFE_STOP)
    assert ev.actor_type.value == "human" and ev.data["actor"] == "hemant"
