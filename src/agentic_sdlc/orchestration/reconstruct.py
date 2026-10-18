"""Rebuild stage state from the event log alone (NFR-04).

Used by the reconstruction test and by ``Engine.resume`` as a cross-check
between the stage table and the event history. If the two disagree, the event
log wins and the discrepancy is recorded.
"""

from __future__ import annotations

from collections.abc import Iterable

from agentic_sdlc.orchestration.events import AuditEvent, EventKind
from agentic_sdlc.orchestration.states import StageState

_EVENT_TO_STATE: dict[EventKind, StageState] = {
    EventKind.STAGE_READY: StageState.READY,
    EventKind.STAGE_STARTED: StageState.RUNNING,
    EventKind.STAGE_SUCCEEDED: StageState.SUCCEEDED,
    EventKind.STAGE_FAILED: StageState.FAILED,
    EventKind.STAGE_SKIPPED: StageState.SKIPPED,
    EventKind.RETRY_SCHEDULED: StageState.RETRYING,
    EventKind.FALLBACK_USED: StageState.FALLBACK,
    EventKind.COMPENSATION_STARTED: StageState.COMPENSATING,
    EventKind.COMPENSATION_COMPLETED: StageState.COMPENSATED,
    EventKind.ROLLBACK_COMPLETED: StageState.COMPENSATED,
    EventKind.ARTIFACT_INVALIDATED: StageState.INVALIDATED,
    EventKind.GATE_OPENED: StageState.READY,
}


def reconstruct_stage_states(
    events: Iterable[AuditEvent],
) -> tuple[dict[str, StageState], dict[str, int]]:
    states: dict[str, StageState] = {}
    attempts: dict[str, int] = {}
    for event in events:
        if event.stage is None:
            continue
        if event.kind is EventKind.STAGE_STARTED:
            attempts[event.stage] = attempts.get(event.stage, 0) + 1
        if event.kind is EventKind.DECISION_RECORDED:
            decision = event.result or ""
            states[event.stage] = (
                StageState.SUCCEEDED if decision in {"approve", "clarify"} else StageState.FAILED
            )
            continue
        if event.kind is EventKind.REPLAN:
            for name in event.data.get("reset", []):
                states[name] = StageState.PENDING
            continue
        mapped = _EVENT_TO_STATE.get(event.kind)
        if mapped is not None:
            states[event.stage] = mapped
    return states, attempts
