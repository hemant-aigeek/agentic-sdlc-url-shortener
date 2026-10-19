"""FR-O08..O13, NFR-02, NFR-03 / ADR-008: bounded retry, timeout, fallback, safe-stop, resume."""

from __future__ import annotations

import time

import pytest

from agentic_sdlc.config import Settings
from agentic_sdlc.orchestration.context import RunContext
from agentic_sdlc.orchestration.events import EventKind
from agentic_sdlc.orchestration.graph import WorkflowGraph
from agentic_sdlc.orchestration.policies import RetryPolicy, TimeoutPolicy
from agentic_sdlc.orchestration.states import RunState, StageState
from agentic_sdlc.orchestration.store import WorkflowStore
from tests.orchestration.conftest import ScriptedAgent, make_engine, permanent, stage, transient

pytestmark = pytest.mark.orchestration

RETRY3 = RetryPolicy(max_attempts=3, base_delay_s=0.01, multiplier=2.0, max_delay_s=0.05)


def chain(_: RunContext) -> WorkflowGraph:
    return WorkflowGraph.build([stage("a"), stage("b", "a", retry=RETRY3), stage("c", "b")])


def with_fallback(_: RunContext) -> WorkflowGraph:
    return WorkflowGraph.build(
        [stage("a"), stage("b", "a", retry=RETRY3, fallback="fallback"), stage("c", "b")]
    )


def with_timeout(_: RunContext) -> WorkflowGraph:
    return WorkflowGraph.build(
        [
            stage(
                "slow",
                retry=RetryPolicy(max_attempts=2, base_delay_s=0.01),
                timeout=TimeoutPolicy(seconds=0.2),
            )
        ]
    )


@pytest.mark.req("FR-O08", "NFR-02")
def test_transient_failure_is_retried_with_backoff_and_recorded(
    store: WorkflowStore, agent: ScriptedAgent, settings: Settings
) -> None:
    agent.failures["b"] = [transient("db hiccup"), transient("db hiccup again")]
    sleeps: list[float] = []
    engine = make_engine(store, agent, settings, {"g": chain}, sleep=sleeps.append)
    run_id = engine.start(title="t", requirement="r", scope="greenfield", planner="g")
    run = engine.run(run_id)
    assert run.state is RunState.COMPLETED
    assert [c.attempt for c in agent.calls if c.stage == "b"] == [1, 2, 3]
    assert sleeps == [0.01, 0.02]  # exponential backoff between attempts
    b = store.load_stages(run_id)["b"]
    assert b.state is StageState.SUCCEEDED and b.attempt == 3
    kinds = [e.kind for e in store.list_events(run_id) if e.stage == "b"]
    assert kinds.count(EventKind.RETRY_SCHEDULED) == 2
    assert kinds.count(EventKind.FAILURE_DETECTED) == 1
    assert kinds.index(EventKind.RECOVERY_STARTED) < kinds.index(EventKind.RECOVERY_COMPLETED)
    retry = next(e for e in store.list_events(run_id) if e.kind is EventKind.RETRY_SCHEDULED)
    assert (
        retry.data["max_attempts"] == 3
        and retry.data["next_attempt"] == 2
        and retry.reason == "db hiccup"
    )


@pytest.mark.req("FR-O08", "FR-O12")
def test_retries_are_bounded_then_safe_stop(
    store: WorkflowStore, agent: ScriptedAgent, settings: Settings
) -> None:
    agent.failures["b"] = [transient("x")] * 10
    engine = make_engine(store, agent, settings, {"g": chain})
    run_id = engine.start(title="t", requirement="r", scope="greenfield", planner="g")
    run = engine.run(run_id)
    assert run.state is RunState.SAFE_STOPPED
    assert run.terminal_reason is not None and run.terminal_reason.startswith("RETRIES_EXHAUSTED")
    assert len([c for c in agent.calls if c.stage == "b"]) == 3  # exactly max_attempts, not 10
    assert store.load_stages(run_id)["c"].state is StageState.PENDING
    assert store.load_stages(run_id)["b"].failure_kind == "TRANSIENT"
    assert engine.run(run_id).state is RunState.SAFE_STOPPED  # terminal, deterministic


@pytest.mark.req("FR-O08")
def test_permanent_failure_is_never_retried(
    store: WorkflowStore, agent: ScriptedAgent, settings: Settings
) -> None:
    agent.failures["b"] = [permanent("schema mismatch")]
    engine = make_engine(store, agent, settings, {"g": chain})
    run_id = engine.start(title="t", requirement="r", scope="greenfield", planner="g")
    run = engine.run(run_id)
    assert run.state is RunState.SAFE_STOPPED
    assert len([c for c in agent.calls if c.stage == "b"]) == 1
    failed = next(e for e in store.list_events(run_id) if e.kind is EventKind.STAGE_FAILED)
    assert failed.data["failure_kind"] == "PERMANENT" and failed.data["retry_eligible"] is False


@pytest.mark.req("FR-O09")
def test_timeout_counts_as_transient_and_is_bounded(
    store: WorkflowStore, agent: ScriptedAgent, settings: Settings
) -> None:
    agent.sleep_s = 0.5  # every attempt exceeds the 0.2s timeout
    engine = make_engine(store, agent, settings, {"g": with_timeout})
    run_id = engine.start(title="t", requirement="r", scope="greenfield", planner="g")
    t0 = time.monotonic()
    run = engine.run(run_id)
    assert run.state is RunState.SAFE_STOPPED
    assert time.monotonic() - t0 < 2.0  # two attempts x 0.2s, not 2 x 0.5s
    kinds = [e.kind for e in store.list_events(run_id)]
    assert kinds.count(EventKind.STAGE_TIMED_OUT) == 2
    assert store.load_stages(run_id)["slow"].failure_kind == "TRANSIENT"


@pytest.mark.req("FR-O10")
def test_fallback_runs_after_exhaustion_and_is_flagged(
    store: WorkflowStore, agent: ScriptedAgent, settings: Settings
) -> None:
    agent.failures["b"] = [transient("x")] * 3
    engine = make_engine(store, agent, settings, {"g": with_fallback})
    run_id = engine.start(title="t", requirement="r", scope="greenfield", planner="g")
    run = engine.run(run_id)
    assert run.state is RunState.COMPLETED
    b = store.load_stages(run_id)["b"]
    assert b.state is StageState.FALLBACK and b.fallback_used is True
    assert (
        run.context.outputs["b"]["fallback"] is True
        and run.context.outputs["b"]["primary_error"] == "x"
    )
    assert [c.stage for c in agent.calls][-1] == "c"  # dependants proceeded on the fallback result
    kinds = [e.kind for e in store.list_events(run_id) if e.stage == "b"]
    assert EventKind.FALLBACK_USED in kinds and kinds[-1] is EventKind.RECOVERY_COMPLETED
    rec = next(e for e in store.list_events(run_id) if e.kind is EventKind.RECOVERY_COMPLETED)
    assert rec.data["mechanism"] == "fallback"


@pytest.mark.req("FR-O12")
def test_fallback_failure_safe_stops(
    store: WorkflowStore, agent: ScriptedAgent, settings: Settings
) -> None:
    agent.failures["b"] = [transient("x")] * 3 + [permanent("fallback broke")]
    engine = make_engine(store, agent, settings, {"g": with_fallback})
    run_id = engine.start(title="t", requirement="r", scope="greenfield", planner="g")
    run = engine.run(run_id)
    assert run.state is RunState.SAFE_STOPPED and run.terminal_reason is not None
    assert run.terminal_reason.startswith("FALLBACK_FAILED")


@pytest.mark.req("FR-O08")
def test_succeeded_stage_is_not_re_executed(
    store: WorkflowStore, agent: ScriptedAgent, settings: Settings
) -> None:
    engine = make_engine(store, agent, settings, {"g": chain})
    run_id = engine.start(title="t", requirement="r", scope="greenfield", planner="g")
    engine.run(run_id)
    calls = len(agent.calls)
    engine.run(run_id)
    engine.resume(run_id)
    assert len(agent.calls) == calls


@pytest.mark.req("FR-O12")
def test_illegal_transition_is_a_safe_stop_not_a_crash(
    store: WorkflowStore, agent: ScriptedAgent, settings: Settings
) -> None:
    from agentic_sdlc.errors import IllegalTransitionError

    engine = make_engine(store, agent, settings, {"g": chain})
    run_id = engine.start(title="t", requirement="r", scope="greenfield", planner="g")
    engine.run(run_id)
    with pytest.raises(IllegalTransitionError):
        engine.replan(run_id, trigger="late change")  # COMPLETED is terminal
    assert engine.load(run_id).state is RunState.COMPLETED


@pytest.mark.req("FR-O13", "NFR-03")
def test_resume_after_crash_retries_interrupted_stage_without_re_running_succeeded_ones(
    store: WorkflowStore, agent: ScriptedAgent, settings: Settings
) -> None:
    engine = make_engine(store, agent, settings, {"g": chain})
    run_id = engine.start(title="t", requirement="r", scope="greenfield", planner="g")
    engine.run(run_id, max_batches=1)  # a done, suspended
    assert engine.load(run_id).state is RunState.SUSPENDED
    # simulate a crash mid-attempt of b: the row says RUNNING, nothing finished it
    b = store.load_stages(run_id)["b"]
    b.state, b.attempt = StageState.RUNNING, 1
    store.save_stage(b)
    run2 = store.load_run(run_id)
    assert run2 is not None
    run2.state = RunState.RUNNING
    store.save_run(run2)

    fresh = make_engine(store, ScriptedAgent(), settings, {"g": chain})  # new process, new agent
    run = fresh.resume(run_id)
    assert run.state is RunState.COMPLETED
    stages = store.load_stages(run_id)
    assert stages["b"].attempt == 2 and stages["b"].state is StageState.SUCCEEDED
    assert [c.stage for c in agent.calls] == ["a"]  # the old process never re-ran a
    events = store.list_events(run_id)
    resumed = next(e for e in events if e.kind is EventKind.RUN_RESUMED)
    assert resumed.data["interrupted_stages"] == ["b"]


@pytest.mark.req("FR-O13")
def test_suspend_and_resume_from_persisted_state_with_new_engine(
    store: WorkflowStore, agent: ScriptedAgent, settings: Settings
) -> None:
    engine = make_engine(store, agent, settings, {"g": chain})
    run_id = engine.start(title="t", requirement="r", scope="greenfield", planner="g")
    assert engine.run(run_id, max_batches=2).state is RunState.SUSPENDED
    kinds = [e.kind for e in store.list_events(run_id)]
    assert EventKind.RUN_SUSPENDED in kinds
    other = make_engine(store, agent, settings, {"g": chain})
    assert other.resume(run_id).state is RunState.COMPLETED
    assert [c.stage for c in agent.calls] == ["a", "b", "c"]


@pytest.mark.req("FR-O08", "FR-O10", "NFR-02")
def test_concurrent_run_calls_on_one_run_execute_each_stage_once(
    store: WorkflowStore, agent: ScriptedAgent, settings: Settings
) -> None:
    """Duplicate-execution protection: two callers advancing the same run must not
    both execute a ready stage (found in the pre-submission review)."""
    import threading

    agent.sleep_s = 0.05  # make the window wide enough for the race to show
    engine = make_engine(store, agent, settings, {"g": chain})
    run_id = engine.start(title="t", requirement="r", scope="greenfield", planner="g")
    errors: list[BaseException] = []

    def advance() -> None:
        try:
            engine.run(run_id)
        except BaseException as exc:  # noqa: BLE001 - we want every failure recorded
            errors.append(exc)

    threads = [threading.Thread(target=advance) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert store.load_run(run_id).state is RunState.COMPLETED
    started = [e.stage for e in store.list_events(run_id) if e.kind is EventKind.STAGE_STARTED]
    assert sorted(started) == ["a", "b", "c"], started
    assert [c.stage for c in agent.calls] == ["a", "b", "c"]
