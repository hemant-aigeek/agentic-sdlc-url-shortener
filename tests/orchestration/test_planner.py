"""Planner shape per scope (FR-O02, FR-O04, SCN-A/B/C; ADR-005)."""

from __future__ import annotations

import pytest

from agentic_sdlc.config import Settings
from agentic_sdlc.orchestration.context import RunContext
from agentic_sdlc.orchestration.planner import make_planner


def ctx(scope: str, **data: object) -> RunContext:
    return RunContext(run_id="r", title="t", scope=scope, requirement_raw="x", data=dict(data))


@pytest.fixture
def plan() -> object:
    return make_planner(Settings(gate_timeout_s=None, log_json=False))


@pytest.mark.req("FR-O02", "SCN-A")
def test_greenfield_graph_has_no_impact_node_but_keeps_escalation_path(plan: object) -> None:
    g = plan(ctx("greenfield"))  # type: ignore[operator]
    names = g.names()
    assert "impact_analysis" not in names
    assert g.stage("clarification").is_conditional  # escalation only if ambiguity emerges
    assert g.stage("decompose").depends_on == ("clarification",)
    assert g.gates() == [
        "clarification",
        "design_approval",
        "policy_exception",
        "release_readiness",
    ]


@pytest.mark.req("FR-O02", "FR-O04", "SCN-B")
def test_brownfield_graph_puts_impact_analysis_before_decompose(plan: object) -> None:
    g = plan(ctx("brownfield"))  # type: ignore[operator]
    order = g.topological_order()
    assert order.index("impact_analysis") < order.index("decompose")
    assert g.stage("decompose").depends_on == ("impact_analysis",)
    assert g.stage("impact_analysis").condition_label == "scope == brownfield"
    assert g.evaluate_condition("impact_analysis", {"scope": "brownfield"})
    assert not g.evaluate_condition("impact_analysis", {"scope": "greenfield"})


@pytest.mark.req("FR-O03", "SC-04")
def test_every_graph_has_fan_out_groups_and_joins(plan: object) -> None:
    for scope in ("greenfield", "brownfield", "ambiguous", "auto"):
        g = plan(ctx(scope))  # type: ignore[operator]
        groups = g.parallel_groups()
        assert {groups.get("implement"), groups.get("test_plan"), groups.get("docs_draft")} == {
            "after:design_approval"
        }
        assert set(g.stage("verify").depends_on) == {"implement", "test_plan", "docs_draft"}
        # compliance evaluates the security outcome, so it must follow the review
        assert set(g.stage("compliance_check").depends_on) == {"verify", "security_review"}
        assert g.stage("policy_exception").depends_on == ("compliance_check",)


@pytest.mark.req("FR-O14", "SCN-C", "ADR-009")
def test_clarification_adds_requirement_revision_and_rewires_downstream(plan: object) -> None:
    before = plan(ctx("ambiguous"))  # type: ignore[operator]
    after = plan(ctx("ambiguous", clarifications=[{"answers": {}}]))  # type: ignore[operator]
    diff = before.diff(after)
    assert diff.added == {"requirement_revision"}
    assert "impact_analysis" in diff.changed  # its dependency moved to requirement_revision
    assert after.stage("requirement_revision").depends_on == ("clarification",)
    assert after.stage("impact_analysis").depends_on == ("requirement_revision",)


@pytest.mark.req("FR-G01", "NFR-11")
def test_gates_are_human_owned_and_policy_exception_is_conditional(plan: object) -> None:
    g = plan(ctx("auto"))  # type: ignore[operator]
    for gate in g.gates():
        assert g.stage(gate).owner == "human"
    assert g.stage("policy_exception").condition_label == "compliance_check.blocking non-empty"
    assert g.evaluate_condition("policy_exception", {"policy_blocking": ["SEC-003"]})
    assert not g.evaluate_condition("policy_exception", {"policy_blocking": []})
    assert g.stage("clarification").gate_kind == "clarification"
    assert g.stage("implement").compensable and g.stage("security_review").fallback
