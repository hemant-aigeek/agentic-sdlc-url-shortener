"""FR-O05 / ADR-006: run and stage state machines with explicit, closed transition tables."""

from __future__ import annotations

import pytest

from agentic_sdlc.errors import IllegalTransitionError
from agentic_sdlc.orchestration.states import (
    RUN_TRANSITIONS,
    STAGE_TRANSITIONS,
    RunState,
    StageState,
    assert_run_transition,
    assert_stage_transition,
)

pytestmark = pytest.mark.unit


@pytest.mark.req("FR-O05")
def test_terminal_run_states_have_no_exits() -> None:
    for state in (RunState.COMPLETED, RunState.FAILED, RunState.REJECTED, RunState.SAFE_STOPPED):
        assert state.is_terminal
        assert RUN_TRANSITIONS[state] == frozenset()


@pytest.mark.req("FR-O05")
@pytest.mark.parametrize(
    ("src", "dst"),
    [
        (RunState.CREATED, RunState.RUNNING),
        (RunState.RUNNING, RunState.WAITING_APPROVAL),
        (RunState.RUNNING, RunState.WAITING_CLARIFICATION),
        (RunState.RUNNING, RunState.SAFE_STOPPED),
        (RunState.RUNNING, RunState.COMPLETED),
        (RunState.WAITING_APPROVAL, RunState.RUNNING),
        (RunState.WAITING_APPROVAL, RunState.REJECTED),
        (RunState.WAITING_APPROVAL, RunState.SAFE_STOPPED),
        (RunState.WAITING_CLARIFICATION, RunState.REPLANNING),
        (RunState.REPLANNING, RunState.RUNNING),
        (RunState.SUSPENDED, RunState.RUNNING),
    ],
)
def test_allowed_run_transitions(src: RunState, dst: RunState) -> None:
    assert_run_transition(src, dst)


@pytest.mark.req("FR-O05")
@pytest.mark.parametrize(
    ("src", "dst"),
    [
        (RunState.CREATED, RunState.COMPLETED),  # cannot complete without running
        (RunState.WAITING_APPROVAL, RunState.COMPLETED),  # cannot skip past a gate
        (RunState.WAITING_CLARIFICATION, RunState.RUNNING),  # must replan first
        (RunState.COMPLETED, RunState.RUNNING),
        (RunState.SAFE_STOPPED, RunState.RUNNING),
        (RunState.REJECTED, RunState.WAITING_APPROVAL),
    ],
)
def test_illegal_run_transitions_raise(src: RunState, dst: RunState) -> None:
    with pytest.raises(IllegalTransitionError) as exc:
        assert_run_transition(src, dst)
    assert src.value in exc.value.detail and dst.value in exc.value.detail


@pytest.mark.req("FR-O05")
@pytest.mark.parametrize(
    ("src", "dst"),
    [
        (StageState.PENDING, StageState.READY),
        (StageState.PENDING, StageState.SKIPPED),
        (StageState.READY, StageState.RUNNING),
        (StageState.RUNNING, StageState.SUCCEEDED),
        (StageState.RUNNING, StageState.FAILED),
        (StageState.RUNNING, StageState.RETRYING),
        (StageState.RETRYING, StageState.RUNNING),
        (StageState.FAILED, StageState.FALLBACK),
        (StageState.SUCCEEDED, StageState.COMPENSATING),
        (StageState.FALLBACK, StageState.COMPENSATING),
        (StageState.COMPENSATING, StageState.COMPENSATED),
        (StageState.SUCCEEDED, StageState.INVALIDATED),
        (StageState.PENDING, StageState.INVALIDATED),
        (StageState.INVALIDATED, StageState.PENDING),
        (StageState.RUNNING, StageState.RETRYING),
    ],
)
def test_allowed_stage_transitions(src: StageState, dst: StageState) -> None:
    assert_stage_transition(src, dst)


@pytest.mark.req("FR-O05")
@pytest.mark.parametrize(
    ("src", "dst"),
    [
        (StageState.PENDING, StageState.RUNNING),  # must pass through READY
        (StageState.PENDING, StageState.SUCCEEDED),
        (StageState.SUCCEEDED, StageState.RUNNING),  # no re-execution of done work
        (StageState.FAILED, StageState.SUCCEEDED),
        (StageState.COMPENSATED, StageState.RUNNING),
        (StageState.SKIPPED, StageState.RUNNING),
    ],
)
def test_illegal_stage_transitions_raise(src: StageState, dst: StageState) -> None:
    with pytest.raises(IllegalTransitionError):
        assert_stage_transition(src, dst)


@pytest.mark.req("FR-O05")
def test_every_state_has_a_transition_entry() -> None:
    assert set(RUN_TRANSITIONS) == set(RunState)
    assert set(STAGE_TRANSITIONS) == set(StageState)
