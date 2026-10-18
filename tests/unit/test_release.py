"""Release-readiness rule (FR-G08, FR-G09, FR-G10)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from agentic_sdlc.orchestration.release import (
    NOT_READY,
    READY,
    READY_WITH_LIMITATIONS,
    compute_release_decision,
)
from agentic_sdlc.orchestration.states import RunState, StageState
from agentic_sdlc.orchestration.store import PolicyEvaluationRecord, PolicyExceptionRecord

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)
MANDATORY = {"SEC-002": True, "SEC-003": True, "DEP-001": False}


def ev(pid: str, outcome: str) -> PolicyEvaluationRecord:
    return PolicyEvaluationRecord("r", "compliance_check", pid, "1.0.0", outcome, "d", NOW)


def exc(
    pid: str, status: str = "approved", expires: datetime | None = NOW + timedelta(days=1)
) -> PolicyExceptionRecord:
    return PolicyExceptionRecord("r", pid, "run", "why", "hemant", "control", NOW, expires, status)


def decide(**kw: object) -> dict[str, object]:
    base: dict[str, object] = dict(
        run_state=RunState.WAITING_APPROVAL,
        stage_states={"verify": StageState.SUCCEEDED},
        evaluations=[ev("SEC-002", "PASS"), ev("SEC-003", "PASS"), ev("DEP-001", "PASS")],
        exceptions=[],
        mandatory=MANDATORY,
        now=NOW,
    )
    base.update(kw)
    return compute_release_decision(**base)  # type: ignore[arg-type]


@pytest.mark.req("FR-G10")
def test_all_pass_is_ready() -> None:
    assert decide()["decision"] == READY


@pytest.mark.req("FR-G08", "FR-G10")
def test_mandatory_fail_without_exception_is_not_ready_and_names_policy() -> None:
    d = decide(evaluations=[ev("SEC-002", "FAIL")])
    assert d["decision"] == NOT_READY and d["blocking_policies"] == ["SEC-002"]


@pytest.mark.req("FR-G08", "FR-G10")
def test_advisory_fail_does_not_block() -> None:
    d = decide(evaluations=[ev("SEC-002", "PASS"), ev("DEP-001", "FAIL")])
    assert d["decision"] == READY


@pytest.mark.req("FR-G09", "FR-G10")
def test_active_exception_yields_ready_with_accepted_limitations() -> None:
    d = decide(evaluations=[ev("SEC-003", "EXCEPTION-REQUESTED")], exceptions=[exc("SEC-003")])
    assert d["decision"] == READY_WITH_LIMITATIONS
    assert d["accepted_exceptions"][0]["policy_id"] == "SEC-003"


@pytest.mark.req("FR-G09")
@pytest.mark.parametrize(
    "exception",
    [exc("SEC-003", status="requested"), exc("SEC-003", expires=NOW - timedelta(seconds=1))],
)
def test_unapproved_or_expired_exception_behaves_as_fail(exception: PolicyExceptionRecord) -> None:
    d = decide(evaluations=[ev("SEC-003", "EXCEPTION-REQUESTED")], exceptions=[exception])
    assert d["decision"] == NOT_READY and "SEC-003" in d["blocking_policies"]


@pytest.mark.req("FR-G10")
def test_fallback_stage_is_an_accepted_limitation() -> None:
    d = decide(
        stage_states={"verify": StageState.SUCCEEDED, "security_review": StageState.FALLBACK}
    )
    assert d["decision"] == READY_WITH_LIMITATIONS and d["fallback_stages"] == ["security_review"]


@pytest.mark.req("FR-G10", "FR-O12")
def test_terminated_run_or_missing_verification_is_not_ready() -> None:
    assert decide(run_state=RunState.SAFE_STOPPED)["decision"] == NOT_READY
    assert decide(stage_states={"verify": StageState.FAILED})["decision"] == NOT_READY
    assert decide(evaluations=[])["decision"] == NOT_READY
