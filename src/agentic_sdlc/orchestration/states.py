"""Run and stage state machines (FR-O05, ADR-006).

The transition tables are *closed*: anything not listed raises
``IllegalTransitionError``, and the engine treats that as a safe-stop
condition rather than a bug to paper over. Keeping the tables as data makes
them inspectable by tests, documentation and the API.
"""

from __future__ import annotations

from enum import StrEnum

from agentic_sdlc.errors import IllegalTransitionError


class RunState(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    WAITING_CLARIFICATION = "WAITING_CLARIFICATION"
    REPLANNING = "REPLANNING"
    SUSPENDED = "SUSPENDED"
    SAFE_STOPPED = "SAFE_STOPPED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"

    @property
    def is_terminal(self) -> bool:
        return self in _TERMINAL_RUN

    @property
    def is_waiting(self) -> bool:
        return self in {RunState.WAITING_APPROVAL, RunState.WAITING_CLARIFICATION}


class StageState(StrEnum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    FALLBACK = "FALLBACK"
    COMPENSATING = "COMPENSATING"
    COMPENSATED = "COMPENSATED"
    SKIPPED = "SKIPPED"
    INVALIDATED = "INVALIDATED"

    @property
    def satisfies_dependency(self) -> bool:
        """A dependant may start when its dependency is in one of these states."""
        return self in {StageState.SUCCEEDED, StageState.FALLBACK, StageState.SKIPPED}

    @property
    def is_done(self) -> bool:
        return self in {
            StageState.SUCCEEDED,
            StageState.FAILED,
            StageState.FALLBACK,
            StageState.COMPENSATED,
            StageState.SKIPPED,
        }


_TERMINAL_RUN = frozenset(
    {RunState.SAFE_STOPPED, RunState.COMPLETED, RunState.FAILED, RunState.REJECTED}
)

RUN_TRANSITIONS: dict[RunState, frozenset[RunState]] = {
    RunState.CREATED: frozenset({RunState.RUNNING, RunState.SAFE_STOPPED}),
    RunState.RUNNING: frozenset(
        {
            RunState.WAITING_APPROVAL,
            RunState.WAITING_CLARIFICATION,
            RunState.REPLANNING,
            RunState.SUSPENDED,
            RunState.SAFE_STOPPED,
            RunState.COMPLETED,
            RunState.FAILED,
        }
    ),
    RunState.WAITING_APPROVAL: frozenset(
        {RunState.RUNNING, RunState.REJECTED, RunState.SAFE_STOPPED, RunState.REPLANNING}
    ),
    RunState.WAITING_CLARIFICATION: frozenset({RunState.REPLANNING, RunState.SAFE_STOPPED}),
    RunState.REPLANNING: frozenset({RunState.RUNNING, RunState.SAFE_STOPPED}),
    RunState.SUSPENDED: frozenset({RunState.RUNNING, RunState.SAFE_STOPPED}),
    RunState.SAFE_STOPPED: frozenset(),
    RunState.COMPLETED: frozenset(),
    RunState.FAILED: frozenset(),
    RunState.REJECTED: frozenset(),
}

STAGE_TRANSITIONS: dict[StageState, frozenset[StageState]] = {
    StageState.PENDING: frozenset({StageState.READY, StageState.SKIPPED, StageState.INVALIDATED}),
    StageState.READY: frozenset({StageState.RUNNING, StageState.INVALIDATED}),
    StageState.RUNNING: frozenset(
        {StageState.SUCCEEDED, StageState.FAILED, StageState.RETRYING, StageState.INVALIDATED}
    ),
    StageState.RETRYING: frozenset({StageState.RUNNING, StageState.INVALIDATED}),
    StageState.FAILED: frozenset({StageState.FALLBACK, StageState.INVALIDATED}),
    StageState.SUCCEEDED: frozenset({StageState.COMPENSATING, StageState.INVALIDATED}),
    StageState.FALLBACK: frozenset({StageState.COMPENSATING, StageState.INVALIDATED}),
    StageState.COMPENSATING: frozenset({StageState.COMPENSATED}),
    StageState.COMPENSATED: frozenset({StageState.INVALIDATED}),
    StageState.SKIPPED: frozenset({StageState.INVALIDATED}),
    StageState.INVALIDATED: frozenset({StageState.PENDING}),
}


def assert_run_transition(src: RunState, dst: RunState) -> None:
    if dst not in RUN_TRANSITIONS[src]:
        raise IllegalTransitionError(f"run transition {src.value} -> {dst.value} is not allowed")


def assert_stage_transition(src: StageState, dst: StageState) -> None:
    if dst not in STAGE_TRANSITIONS[src]:
        raise IllegalTransitionError(f"stage transition {src.value} -> {dst.value} is not allowed")
