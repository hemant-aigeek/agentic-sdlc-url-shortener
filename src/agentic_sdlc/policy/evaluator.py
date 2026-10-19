"""Policy evaluation and blocking semantics (FR-G06..G09).

``evaluate`` runs every registered policy against a ``PolicyInput`` and
returns one outcome per policy. ``blocking`` applies the governance rule:
a mandatory FAIL or EXCEPTION-REQUESTED blocks unless an *approved, unexpired*
exception for that policy exists; advisory policies never block.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from agentic_sdlc.orchestration.context import RunContext
from agentic_sdlc.orchestration.events import AuditEvent
from agentic_sdlc.orchestration.store import PolicyExceptionRecord
from agentic_sdlc.policy.model import Outcome, Policy, PolicyEvaluation
from agentic_sdlc.policy.registry import POLICIES, POLICY_VERSION


@dataclass
class PolicyInput:
    ctx: RunContext
    artifacts: dict[str, dict[str, Any]]  # kind -> latest live content
    events: list[AuditEvent]
    exceptions: list[PolicyExceptionRecord]
    forced_fail: str | None = None  # demonstration fault: force this policy id to FAIL
    extra: dict[str, Any] = field(default_factory=dict)


def evaluate(inp: PolicyInput, policies: list[Policy] | None = None) -> list[PolicyEvaluation]:
    out: list[PolicyEvaluation] = []
    for policy in policies or POLICIES:
        if inp.forced_fail == policy.id:
            outcome, detail = (
                Outcome.FAIL,
                "injected demonstration fault (settings.demo_fault_policy_fail)",
            )
        else:
            try:
                outcome, detail = policy.check(inp)
            except Exception as exc:  # a broken check must never pass silently
                outcome, detail = Outcome.FAIL, f"policy check raised {type(exc).__name__}: {exc}"
        out.append(
            PolicyEvaluation(
                policy_id=policy.id,
                policy_version=POLICY_VERSION,
                outcome=outcome,
                detail=detail,
                mandatory=policy.mandatory,
                exceptionable=policy.exceptionable,
            )
        )
    return out


def exception_is_active(exc: PolicyExceptionRecord, now: datetime) -> bool:
    if exc.status != "approved":
        return False
    return exc.expires_at is None or exc.expires_at > now


def blocking(
    evaluations: list[PolicyEvaluation],
    *,
    exceptions: list[PolicyExceptionRecord],
    now: datetime | None = None,
) -> list[PolicyEvaluation]:
    now = now or datetime.now(UTC)
    active = {e.policy_id for e in exceptions if exception_is_active(e, now)}
    return [
        ev
        for ev in evaluations
        if ev.mandatory
        and ev.outcome in {Outcome.FAIL, Outcome.EXCEPTION_REQUESTED}
        # an exception only ever waives an *exceptionable* policy
        and not (ev.exceptionable and ev.policy_id in active)
    ]
