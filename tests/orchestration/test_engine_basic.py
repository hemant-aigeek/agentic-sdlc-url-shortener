"""FR-O01, FR-O03, FR-O04, FR-O06, FR-O07, SC-04: the scheduler executes the graph, not a list."""

from __future__ import annotations

from typing import Any

import pytest

from agentic_sdlc.config import Settings
from agentic_sdlc.orchestration.context import RunContext
from agentic_sdlc.orchestration.events import EventKind
from agentic_sdlc.orchestration.graph import WorkflowGraph
from agentic_sdlc.orchestration.states import RunState, StageState
from agentic_sdlc.orchestration.store import WorkflowStore
from tests.orchestration.conftest import ScriptedAgent, make_engine, stage

pytestmark = pytest.mark.orchestration


def diamond(_: RunContext) -> WorkflowGraph:
    return WorkflowGraph.build([stage("a"), stage("b", "a"), stage("c", "a"), stage("d", "b", "c")])


def chain_with_condition(ctx: RunContext) -> WorkflowGraph:
    return WorkflowGraph.build(
        [
            stage("a"),
            stage(
                "clarify",
                "a",
                condition=lambda m: bool(m.get("needs_clarification")),
                condition_label="needs_clarification",
            ),
            stage("b", "clarify"),
        ]
    )


@pytest.mark.req("FR-O01")
def test_start_creates_persisted_run_with_graph_and_correlation_id(
    store: WorkflowStore, agent: ScriptedAgent, settings: Settings
) -> None:
    engine = make_engine(store, agent, settings, {"diamond": diamond})
    run_id = engine.start(title="t", requirement="do x", scope="greenfield", planner="diamond")
    run = store.load_run(run_id)
    assert run is not None and run.state is RunState.CREATED
    assert len(run_id) >= 16
    stages = store.load_stages(run_id)
    assert set(stages) == {"a", "b", "c", "d"} and all(
        s.state is StageState.PENDING for s in stages.values()
    )
    edges = store.load_edges(run_id, 1)
    assert {(e.from_stage, e.to_stage) for e in edges} == {
        ("a", "b"),
        ("a", "c"),
        ("b", "d"),
        ("c", "d"),
    }
    assert store.list_events(run_id)[0].kind is EventKind.RUN_CREATED


@pytest.mark.req("FR-O03")
def test_run_executes_in_dependency_order_and_completes(
    store: WorkflowStore, agent: ScriptedAgent, settings: Settings
) -> None:
    engine = make_engine(store, agent, settings, {"diamond": diamond})
    run_id = engine.start(title="t", requirement="do x", scope="greenfield", planner="diamond")
    run = engine.run(run_id)
    assert run.state is RunState.COMPLETED
    order = [c.stage for c in agent.calls]
    assert order[0] == "a" and order[-1] == "d" and set(order[1:3]) == {"b", "c"}
    assert all(s.state is StageState.SUCCEEDED for s in store.load_stages(run_id).values())


@pytest.mark.req("FR-O03", "SC-04")
def test_independent_stages_execute_in_parallel(
    store: WorkflowStore, agent: ScriptedAgent, settings: Settings
) -> None:
    agent.sleep_s = 0.3
    engine = make_engine(store, agent, settings, {"diamond": diamond})
    run_id = engine.start(title="t", requirement="do x", scope="greenfield", planner="diamond")
    engine.run(run_id)
    b = next(c for c in agent.calls if c.stage == "b")
    c = next(c for c in agent.calls if c.stage == "c")
    # overlap in wall-clock time proves fan-out, not interleaved sequential calls
    assert b.started < c.ended and c.started < b.ended
    stages = store.load_stages(run_id)
    assert stages["b"].parallel_group == stages["c"].parallel_group == "after:a"
    assert stages["b"].started_at is not None and stages["c"].ended_at is not None
    assert (
        stages["b"].started_at < stages["c"].ended_at
        and stages["c"].started_at < stages["b"].ended_at
    )  # type: ignore[operator]


@pytest.mark.req("FR-O03")
def test_join_starts_only_after_all_inputs(
    store: WorkflowStore, agent: ScriptedAgent, settings: Settings
) -> None:
    agent.sleep_s = 0.1
    engine = make_engine(store, agent, settings, {"diamond": diamond})
    run_id = engine.start(title="t", requirement="do x", scope="greenfield", planner="diamond")
    engine.run(run_id)
    d = next(c for c in agent.calls if c.stage == "d")
    assert all(c.ended <= d.started for c in agent.calls if c.stage in {"b", "c"})
    assert d.started >= max(c.ended for c in agent.calls if c.stage in {"b", "c"})


@pytest.mark.req("FR-O04")
def test_conditional_stage_is_skipped_and_dependants_proceed(
    store: WorkflowStore, agent: ScriptedAgent, settings: Settings
) -> None:
    engine = make_engine(store, agent, settings, {"cond": chain_with_condition})
    run_id = engine.start(
        title="t",
        requirement="do x",
        scope="greenfield",
        planner="cond",
        data={"needs_clarification": False},
    )
    run = engine.run(run_id)
    assert run.state is RunState.COMPLETED
    stages = store.load_stages(run_id)
    assert (
        stages["clarify"].state is StageState.SKIPPED and stages["b"].state is StageState.SUCCEEDED
    )
    assert [c.stage for c in agent.calls] == ["a", "b"]
    kinds = [e.kind for e in store.list_events(run_id)]
    assert EventKind.STAGE_SKIPPED in kinds


@pytest.mark.req("FR-O04")
def test_conditional_stage_runs_when_condition_true(
    store: WorkflowStore, agent: ScriptedAgent, settings: Settings
) -> None:
    engine = make_engine(store, agent, settings, {"cond": chain_with_condition})
    run_id = engine.start(
        title="t",
        requirement="do x",
        scope="greenfield",
        planner="cond",
        data={"needs_clarification": True},
    )
    engine.run(run_id)
    assert [c.stage for c in agent.calls] == ["a", "clarify", "b"]


@pytest.mark.req("FR-O06", "FR-O07")
def test_outputs_and_artifacts_propagate_with_lineage(
    store: WorkflowStore, agent: ScriptedAgent, settings: Settings
) -> None:
    engine = make_engine(store, agent, settings, {"diamond": diamond})
    run_id = engine.start(title="t", requirement="do x", scope="greenfield", planner="diamond")
    engine.run(run_id)
    run = store.load_run(run_id)
    assert run is not None
    # d saw the outputs of everything upstream
    assert run.context.outputs["d"]["saw_outputs"] == ["a", "b", "c"]
    arts = {a.kind: a for a in store.list_artifacts(run_id)}
    assert set(arts) == {"a_artifact", "b_artifact", "c_artifact", "d_artifact"}
    # lineage: d's artifact derives from b's and c's artifacts
    assert sorted(arts["d_artifact"].derived_from) == sorted(
        [arts["b_artifact"].id, arts["c_artifact"].id]
    )  # type: ignore[list-item]
    assert arts["d_artifact"].policy_version == run.policy_version


@pytest.mark.req("FR-O20")
def test_events_record_actor_action_target_result_and_reason(
    store: WorkflowStore, agent: ScriptedAgent, settings: Settings
) -> None:
    engine = make_engine(store, agent, settings, {"diamond": diamond})
    run_id = engine.start(title="t", requirement="do x", scope="greenfield", planner="diamond")
    engine.run(run_id)
    events = store.list_events(run_id)
    kinds = [e.kind for e in events]
    assert kinds[0] is EventKind.RUN_CREATED and kinds[-1] is EventKind.RUN_COMPLETED
    assert kinds.count(EventKind.STAGE_STARTED) == 4 and kinds.count(EventKind.STAGE_SUCCEEDED) == 4
    started = next(e for e in events if e.kind is EventKind.STAGE_STARTED)
    assert started.actor_type.value == "agent" and started.stage == "a" and started.attempt == 1
    assert all(e.at is not None for e in events)
    assert [e.seq for e in events] == list(range(1, len(events) + 1))


@pytest.mark.req("FR-O05")
def test_permanent_failure_without_fallback_or_retry_safe_stops(
    store: WorkflowStore, agent: ScriptedAgent, settings: Settings
) -> None:
    from tests.orchestration.conftest import permanent

    agent.failures["b"] = [permanent("cannot")]
    engine = make_engine(store, agent, settings, {"diamond": diamond})
    run_id = engine.start(title="t", requirement="do x", scope="greenfield", planner="diamond")
    run = engine.run(run_id)
    assert run.state is RunState.SAFE_STOPPED
    assert run.terminal_reason is not None and "RETRIES_EXHAUSTED" in run.terminal_reason
    stages = store.load_stages(run_id)
    assert stages["b"].state is StageState.FAILED and stages["b"].failure_kind == "PERMANENT"
    assert stages["d"].state is StageState.PENDING  # never started


@pytest.mark.req("FR-O02")
def test_graph_view_is_inspectable(
    store: WorkflowStore, agent: ScriptedAgent, settings: Settings
) -> None:
    engine = make_engine(store, agent, settings, {"diamond": diamond})
    run_id = engine.start(title="t", requirement="do x", scope="greenfield", planner="diamond")
    view: dict[str, Any] = engine.graph_view(run_id)
    assert [s["name"] for s in view["stages"]] == ["a", "b", "c", "d"]
    assert view["stages"][1]["parallel_group"] == "after:a"
    assert view["stages"][0]["state"] == "PENDING"
