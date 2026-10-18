"""Release-readiness determination (FR-G08..G10, constitution VI).

A pure function over persisted facts so the same rule produces the gate
context, the summary and the CLI answer. Exactly one of three decisions is
returned, with the evidence it rests on.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from agentic_sdlc.orchestration.states import RunState, StageState
from agentic_sdlc.orchestration.store import PolicyEvaluationRecord, PolicyExceptionRecord
from agentic_sdlc.policy.evaluator import exception_is_active
from agentic_sdlc.policy.model import Outcome

READY = "READY"
READY_WITH_LIMITATIONS = "READY WITH ACCEPTED LIMITATIONS"
NOT_READY = "NOT READY"


def latest_evaluations(
    evaluations: list[PolicyEvaluationRecord],
) -> dict[str, PolicyEvaluationRecord]:
    latest: dict[str, PolicyEvaluationRecord] = {}
    for ev in evaluations:  # store returns them in insertion order
        latest[ev.policy_id] = ev
    return latest


def compute_release_decision(
    *,
    run_state: RunState,
    stage_states: dict[str, StageState],
    evaluations: list[PolicyEvaluationRecord],
    exceptions: list[PolicyExceptionRecord],
    mandatory: dict[str, bool],
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    latest = latest_evaluations(evaluations)
    active = {e.policy_id: e for e in exceptions if exception_is_active(e, now)}
    inactive = [e for e in exceptions if not exception_is_active(e, now)]
    blocking: list[str] = []
    accepted: list[dict[str, Any]] = []
    for pid, ev in latest.items():
        if ev.outcome not in {Outcome.FAIL.value, Outcome.EXCEPTION_REQUESTED.value}:
            continue
        if not mandatory.get(pid, False):
            continue
        if pid in active:
            exc = active[pid]
            accepted.append(
                {
                    "policy_id": pid,
                    "outcome": ev.outcome,
                    "approver": exc.approver,
                    "compensating_control": exc.compensating_control,
                    "expires_at": exc.expires_at.isoformat() if exc.expires_at else None,
                }
            )
        else:
            blocking.append(pid)
    reasons: list[str] = []
    if blocking:
        reasons.append(
            "mandatory policy failures without an active exception: " + ", ".join(blocking)
        )
    if inactive:
        reasons.append(
            "exceptions that are not active (unapproved/expired): "
            + ", ".join(f"{e.policy_id}({e.status})" for e in inactive)
        )
    if run_state in {RunState.SAFE_STOPPED, RunState.FAILED, RunState.REJECTED}:
        reasons.append(f"run terminated as {run_state.value}")
    if not latest:
        reasons.append("no policy evaluation recorded for this run")
    verify = stage_states.get("verify")
    if verify is not None and verify is not StageState.SUCCEEDED:
        reasons.append(f"verify stage is {verify.value}")
    fallbacks = sorted(n for n, st in stage_states.items() if st is StageState.FALLBACK)

    if reasons:
        decision = NOT_READY
    elif accepted or fallbacks:
        decision = READY_WITH_LIMITATIONS
    else:
        decision = READY
    return {
        "decision": decision,
        "blocking_policies": blocking,
        "accepted_exceptions": accepted,
        "fallback_stages": fallbacks,
        "reasons": reasons,
        "policy_outcomes": {pid: ev.outcome for pid, ev in latest.items()},
        "evaluated_at": now.isoformat(),
    }
