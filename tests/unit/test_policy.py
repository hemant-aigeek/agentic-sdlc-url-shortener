"""FR-G06..G09 / ADR-011: versioned policies, four outcomes, blocking and exception semantics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from agentic_sdlc.orchestration.context import RunContext
from agentic_sdlc.orchestration.events import ActorType, AuditEvent, EventKind
from agentic_sdlc.orchestration.store import PolicyExceptionRecord
from agentic_sdlc.policy.evaluator import PolicyInput, blocking, evaluate
from agentic_sdlc.policy.model import Outcome
from agentic_sdlc.policy.registry import POLICIES, POLICY_VERSION, describe, get_policy

# Assembled at runtime so the repository secret scan (SEC-002) stays strict while
# the policy test still exercises the AWS access-key pattern.
FAKE_AWS_KEY = "AKIA" + "ABCDEFGHIJKLMNOP"

pytestmark = pytest.mark.unit

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


def ctx(scope: str = "greenfield", **data: object) -> RunContext:
    return RunContext(run_id="r", title="t", scope=scope, requirement_raw="req", data=dict(data))


def ev(seq: int, kind: EventKind, stage: str | None, result: str | None = None) -> AuditEvent:
    return AuditEvent(
        "r", seq, kind, ActorType.AGENT, NOW + timedelta(seconds=seq), stage=stage, result=result
    )


def healthy_events() -> list[AuditEvent]:
    return [
        ev(1, EventKind.RUN_CREATED, None),
        ev(2, EventKind.STAGE_STARTED, "ingest"),
        ev(3, EventKind.STAGE_SUCCEEDED, "ingest", "SUCCEEDED"),
        ev(4, EventKind.GATE_OPENED, "design_approval"),
        ev(5, EventKind.DECISION_RECORDED, "design_approval", "approve"),
        ev(6, EventKind.STAGE_STARTED, "implement"),
        ev(7, EventKind.STAGE_SUCCEEDED, "implement", "SUCCEEDED"),
    ]


@pytest.mark.req("FR-G06")
def test_registry_is_versioned_and_described() -> None:
    assert POLICY_VERSION == "1.0.0"
    ids = [p.id for p in POLICIES]
    assert {
        "SEC-001",
        "SEC-002",
        "SEC-003",
        "CMP-001",
        "CMP-002",
        "CHG-001",
        "CHG-002",
        "DEP-001",
        "AUD-001",
    } <= set(ids)
    assert all(p.version == POLICY_VERSION for p in POLICIES)
    catalogue = describe()
    assert {"id", "domain", "mandatory", "exceptionable", "title", "version"} <= set(catalogue[0])


@pytest.mark.req("FR-G06")
def test_every_policy_yields_exactly_one_of_four_outcomes() -> None:
    result = evaluate(PolicyInput(ctx=ctx(), artifacts={}, events=healthy_events(), exceptions=[]))
    assert {r.policy_id for r in result} == {p.id for p in POLICIES}
    assert all(r.outcome in set(Outcome) for r in result)
    assert all(r.policy_version == POLICY_VERSION for r in result)


@pytest.mark.req("FR-G07")
def test_sec_001_fails_when_a_change_set_weakens_url_validation() -> None:
    weakened = {
        "change_set": {
            "files": {
                "src/agentic_sdlc/domain/validation.py": "def validate_target_url(u):\n  return u"
            }
        }
    }
    r = {
        x.policy_id: x
        for x in evaluate(PolicyInput(ctx=ctx(), artifacts=weakened, events=[], exceptions=[]))
    }
    assert r["SEC-001"].outcome is Outcome.FAIL
    intact = {
        "change_set": {
            "files": {
                "src/agentic_sdlc/domain/validation.py": (
                    "ALLOWED_SCHEMES = frozenset({'http', 'https'})\n_BLOCKED_NETWORKS = [...]\n"
                )
            }
        }
    }
    r = {
        x.policy_id: x
        for x in evaluate(PolicyInput(ctx=ctx(), artifacts=intact, events=[], exceptions=[]))
    }
    assert r["SEC-001"].outcome is Outcome.PASS
    r = {
        x.policy_id: x
        for x in evaluate(PolicyInput(ctx=ctx(), artifacts={}, events=[], exceptions=[]))
    }
    assert r["SEC-001"].outcome is Outcome.NOT_APPLICABLE


@pytest.mark.req("FR-G07")
def test_sec_002_fails_on_secret_patterns_in_artifacts() -> None:
    leaky = {"docs": {"text": "export AWS key " + FAKE_AWS_KEY + " now"}}
    r = {
        x.policy_id: x
        for x in evaluate(PolicyInput(ctx=ctx(), artifacts=leaky, events=[], exceptions=[]))
    }
    assert r["SEC-002"].outcome is Outcome.FAIL and "aws-access-key" in r["SEC-002"].detail


@pytest.mark.req("FR-G07")
def test_sec_003_requests_exception_when_security_review_fell_back() -> None:
    events = [*healthy_events(), ev(8, EventKind.FALLBACK_USED, "security_review", "FALLBACK")]
    r = {
        x.policy_id: x
        for x in evaluate(PolicyInput(ctx=ctx(), artifacts={}, events=events, exceptions=[]))
    }
    assert r["SEC-003"].outcome is Outcome.EXCEPTION_REQUESTED


@pytest.mark.req("FR-G07")
def test_cmp_001_fails_when_a_stage_started_without_finishing_or_gate_without_decision() -> None:
    dangling = [*healthy_events(), ev(8, EventKind.STAGE_STARTED, "verify")]
    r = {
        x.policy_id: x
        for x in evaluate(PolicyInput(ctx=ctx(), artifacts={}, events=dangling, exceptions=[]))
    }
    assert r["CMP-001"].outcome is Outcome.FAIL and "verify" in r["CMP-001"].detail
    undecided = healthy_events()[:4]
    r = {
        x.policy_id: x
        for x in evaluate(PolicyInput(ctx=ctx(), artifacts={}, events=undecided, exceptions=[]))
    }
    assert r["CMP-001"].outcome is Outcome.FAIL and "design_approval" in r["CMP-001"].detail


@pytest.mark.req("FR-G07", "NFR-10")
def test_chg_001_requires_impact_analysis_before_implementation_on_brownfield() -> None:
    events = [
        ev(1, EventKind.STAGE_STARTED, "implement"),
        ev(2, EventKind.STAGE_SUCCEEDED, "implement", "SUCCEEDED"),
    ]
    r = {
        x.policy_id: x
        for x in evaluate(
            PolicyInput(ctx=ctx("brownfield"), artifacts={}, events=events, exceptions=[])
        )
    }
    assert r["CHG-001"].outcome is Outcome.FAIL
    ok_events = [
        ev(1, EventKind.STAGE_SUCCEEDED, "impact_analysis", "SUCCEEDED"),
        ev(2, EventKind.STAGE_STARTED, "implement"),
        ev(3, EventKind.STAGE_SUCCEEDED, "implement", "SUCCEEDED"),
    ]
    r = {
        x.policy_id: x
        for x in evaluate(
            PolicyInput(
                ctx=ctx("brownfield"),
                artifacts={"impact_analysis": {"x": 1}},
                events=ok_events,
                exceptions=[],
            )
        )
    }
    assert r["CHG-001"].outcome is Outcome.PASS
    r = {
        x.policy_id: x
        for x in evaluate(
            PolicyInput(ctx=ctx("greenfield"), artifacts={}, events=events, exceptions=[])
        )
    }
    assert r["CHG-001"].outcome is Outcome.NOT_APPLICABLE


@pytest.mark.req("FR-G07", "NFR-10")
def test_chg_002_requires_acknowledged_api_change_at_design_approval() -> None:
    c = ctx()
    c.outputs["design"] = {"api_or_schema_impact": True}
    c.decisions.append({"gate": "design_approval", "decision": "approve", "payload": {}})
    r = {
        x.policy_id: x for x in evaluate(PolicyInput(ctx=c, artifacts={}, events=[], exceptions=[]))
    }
    assert r["CHG-002"].outcome is Outcome.FAIL
    c.decisions[-1]["payload"] = {"api_change_acknowledged": True}
    r = {
        x.policy_id: x for x in evaluate(PolicyInput(ctx=c, artifacts={}, events=[], exceptions=[]))
    }
    assert r["CHG-002"].outcome is Outcome.PASS


@pytest.mark.req("FR-G08")
def test_mandatory_fail_blocks_and_advisory_does_not() -> None:
    assert get_policy("SEC-002").mandatory and not get_policy("DEP-001").mandatory
    leaky = {
        "docs": {"text": FAKE_AWS_KEY},
        "design": {"new_dependencies": [{"name": "x", "license": "GPL-3.0"}]},
    }
    result = evaluate(PolicyInput(ctx=ctx(), artifacts=leaky, events=[], exceptions=[]))
    blocked = blocking(result, exceptions=[], now=NOW)
    assert [b.policy_id for b in blocked] == ["SEC-002"]  # DEP-001 FAIL is advisory
    assert blocked[0].exceptionable is False


@pytest.mark.req("FR-G09")
def test_approved_unexpired_exception_unblocks_but_expired_or_unapproved_behaves_as_fail() -> None:
    events = [ev(1, EventKind.FALLBACK_USED, "security_review", "FALLBACK")]

    def exc(status: str, expires: datetime | None) -> PolicyExceptionRecord:
        return PolicyExceptionRecord(
            "r",
            "SEC-003",
            "this run",
            "manual review done",
            "hemant",
            "manual review record",
            NOW,
            expires,
            status,
        )

    result = evaluate(PolicyInput(ctx=ctx(), artifacts={}, events=events, exceptions=[]))
    assert [b.policy_id for b in blocking(result, exceptions=[], now=NOW)] == ["SEC-003"]
    assert blocking(result, exceptions=[exc("approved", NOW + timedelta(days=30))], now=NOW) == []
    assert [
        b.policy_id
        for b in blocking(result, exceptions=[exc("approved", NOW - timedelta(days=1))], now=NOW)
    ] == ["SEC-003"]
    assert [
        b.policy_id for b in blocking(result, exceptions=[exc("requested", None)], now=NOW)
    ] == ["SEC-003"]


@pytest.mark.req("FR-G06")
def test_injected_demo_fault_forces_fail_and_says_so() -> None:
    result = evaluate(
        PolicyInput(
            ctx=ctx(), artifacts={}, events=healthy_events(), exceptions=[], forced_fail="CMP-002"
        )
    )
    r = {x.policy_id: x for x in result}
    assert (
        r["CMP-002"].outcome is Outcome.FAIL
        and "injected demonstration fault" in r["CMP-002"].detail
    )
