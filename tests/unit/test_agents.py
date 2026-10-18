"""Deterministic SDLC agents (FR-O15..O18, ADR-010).

Each agent is exercised directly with a hand-built RunContext so the tests
pin down what the agent *derives* from the requirement and the repository,
independent of the engine.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from agentic_sdlc.config import Settings
from agentic_sdlc.errors import StageError, TransientStageError
from agentic_sdlc.orchestration.agents.analysis import (
    DecomposeAgent,
    DesignAgent,
    ImpactAnalysisAgent,
)
from agentic_sdlc.orchestration.agents.delivery import (
    DocsDraftAgent,
    ImplementAgent,
    TestPlanAgent,
    VerifyAgent,
)
from agentic_sdlc.orchestration.agents.requirements import (
    IngestAgent,
    QualityCheckAgent,
    RequirementRevisionAgent,
)
from agentic_sdlc.orchestration.context import RunContext

REPO_ROOT = Path(__file__).resolve().parents[2]

GREENFIELD = (
    "Add a per-link analytics summary endpoint GET /api/v1/links/{code}/analytics/summary "
    "returning total redirects, first and last redirect time, and redirects per day. "
    "Unknown codes return 404. Expired links keep their analytics readable."
)
BROWNFIELD = (
    "Expired links must return 410 Gone instead of the current 404, and analytics for "
    "expired links must remain readable."
)
AMBIGUOUS = "Links should expire after a while and be reusable."


def ctx(requirement: str, scope: str = "auto", **data: Any) -> RunContext:
    return RunContext(
        run_id="r1",
        title="t",
        scope=scope,
        requirement_raw=requirement,
        policy_version="1.0.0",
        workspace=None,
        data=dict(data),
    )


def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        repository_root=REPO_ROOT,
        verify_mode="compile",
        log_json=False,
    )


# --- ingest -----------------------------------------------------------------------


@pytest.mark.req("FR-O15")
def test_ingest_normalises_and_classifies_brownfield(tmp_path: Path) -> None:
    out = IngestAgent(settings(tmp_path)).execute(ctx(BROWNFIELD), "ingest", 1)
    norm = out.data_updates["normalized"]
    assert out.data_updates["scope"] == "brownfield"
    assert norm["title"]
    assert len(norm["functional_statements"]) >= 2
    assert any("410" in s for s in norm["functional_statements"])
    assert out.data_updates["audit_retention"]
    assert [k for k, _ in out.artifacts] == ["normalized_requirement"]


@pytest.mark.req("FR-O15")
def test_ingest_classifies_greenfield_and_respects_explicit_scope(tmp_path: Path) -> None:
    agent = IngestAgent(settings(tmp_path))
    assert agent.execute(ctx(GREENFIELD), "ingest", 1).data_updates["scope"] == "greenfield"
    forced = agent.execute(ctx(GREENFIELD, scope="brownfield"), "ingest", 1)
    assert forced.data_updates["scope"] == "brownfield"
    assert forced.data_updates["normalized"]["scope_source"] == "explicit"


# --- quality check ----------------------------------------------------------------


@pytest.mark.req("FR-O15", "SCN-C")
def test_quality_check_detects_vague_duration_and_conflict(tmp_path: Path) -> None:
    s = settings(tmp_path)
    c = ctx(AMBIGUOUS)
    c.data.update(IngestAgent(s).execute(c, "ingest", 1).data_updates)
    out = QualityCheckAgent(s).execute(c, "quality_check", 1)
    ambiguities = out.output["ambiguities"]
    kinds = {a["kind"] for a in ambiguities}
    assert "undefined_quantity" in kinds  # "a while"
    assert "conflict" in kinds  # "reusable" vs short-code uniqueness (FR-U04)
    assert out.output["max_severity"] == "HIGH"
    assert out.data_updates["clarification_required"] is True
    assert all({"id", "severity", "question", "options"} <= set(a) for a in ambiguities)


@pytest.mark.req("FR-O15", "SCN-A")
def test_quality_check_passes_well_defined_requirement_with_reason(tmp_path: Path) -> None:
    s = settings(tmp_path)
    c = ctx(GREENFIELD, scope="greenfield")
    c.data.update(IngestAgent(s).execute(c, "ingest", 1).data_updates)
    out = QualityCheckAgent(s).execute(c, "quality_check", 1)
    assert out.data_updates["clarification_required"] is False
    checks = out.output["checks"]
    assert {"completeness", "consistency", "testability", "boundaries"} <= set(checks)
    assert all(v["passed"] for v in checks.values())
    assert "no clarification" in out.output["reason_no_clarification"].lower()


@pytest.mark.req("FR-O15")
def test_quality_check_flags_out_of_boundary_requirement(tmp_path: Path) -> None:
    s = settings(tmp_path)
    c = ctx("Add user accounts with login so people can manage their links.")
    c.data.update(IngestAgent(s).execute(c, "ingest", 1).data_updates)
    out = QualityCheckAgent(s).execute(c, "quality_check", 1)
    assert out.output["checks"]["boundaries"]["passed"] is False
    assert out.data_updates["clarification_required"] is True


# --- requirement revision (after a clarification) ------------------------------------


@pytest.mark.req("FR-O14", "SCN-C")
def test_revision_applies_clarification_answers_and_clears_ambiguity(tmp_path: Path) -> None:
    s = settings(tmp_path)
    c = ctx(AMBIGUOUS)
    c.data.update(IngestAgent(s).execute(c, "ingest", 1).data_updates)
    q = QualityCheckAgent(s).execute(c, "quality_check", 1)
    c.outputs["quality_check"] = q.output
    c.data.update(q.data_updates)
    answers = {a["id"]: a["options"][0]["id"] for a in q.output["ambiguities"]}
    c.data["clarifications"] = [{"gate": "clarification", "actor": "h", "answers": answers}]
    c.requirement_version = 2
    out = RequirementRevisionAgent(s).execute(c, "requirement_revision", 1)
    norm = out.data_updates["normalized"]
    assert norm["version"] == 2
    assert norm["resolved_ambiguities"] and all(
        r["answer"] for r in norm["resolved_ambiguities"]
    )
    assert out.output["remaining_high_ambiguities"] == []
    assert out.data_updates["clarification_required"] is False


@pytest.mark.req("FR-O14")
def test_revision_refuses_unanswered_high_ambiguity(tmp_path: Path) -> None:
    s = settings(tmp_path)
    c = ctx(AMBIGUOUS)
    c.data.update(IngestAgent(s).execute(c, "ingest", 1).data_updates)
    q = QualityCheckAgent(s).execute(c, "quality_check", 1)
    c.outputs["quality_check"] = q.output
    c.data["clarifications"] = [{"gate": "clarification", "actor": "h", "answers": {}}]
    with pytest.raises(StageError):
        RequirementRevisionAgent(s).execute(c, "requirement_revision", 1)


# --- impact analysis (reads the real repository) ------------------------------------


@pytest.mark.req("FR-O17", "SCN-B")
def test_impact_analysis_lists_real_modules_tests_and_docs(tmp_path: Path) -> None:
    s = settings(tmp_path)
    c = ctx(BROWNFIELD, scope="brownfield")
    c.data.update(IngestAgent(s).execute(c, "ingest", 1).data_updates)
    out = ImpactAnalysisAgent(s).execute(c, "impact_analysis", 1)
    art = dict(out.artifacts)["impact_analysis"]
    modules = art["impacted_modules"]
    assert "src/agentic_sdlc/domain/service.py" in modules
    assert "src/agentic_sdlc/api/routers/redirect.py" in modules
    assert any(t.startswith("tests/") for t in art["impacted_tests"])
    assert any(d.endswith(".md") or d.endswith(".yaml") for d in art["impacted_docs"])
    assert art["impacted_interfaces"]  # OpenAPI paths touched
    assert art["regression_risks"] and art["rollback_considerations"]
    assert art["evidence"]["files_scanned"] > 50
    assert all(Path(REPO_ROOT, m).exists() for m in modules)


@pytest.mark.req("FR-O17")
def test_impact_analysis_is_not_applicable_for_greenfield(tmp_path: Path) -> None:
    s = settings(tmp_path)
    c = ctx(GREENFIELD, scope="greenfield")
    c.data.update(IngestAgent(s).execute(c, "ingest", 1).data_updates)
    out = ImpactAnalysisAgent(s).execute(c, "impact_analysis", 1)
    assert out.output["applicable"] is False


# --- decomposition and design --------------------------------------------------------


@pytest.mark.req("FR-O16")
def test_decompose_produces_dependency_aware_tasks(tmp_path: Path) -> None:
    s = settings(tmp_path)
    c = ctx(GREENFIELD, scope="greenfield")
    c.data.update(IngestAgent(s).execute(c, "ingest", 1).data_updates)
    out = DecomposeAgent(s).execute(c, "decompose", 1)
    tasks = dict(out.artifacts)["decomposition"]["tasks"]
    ids = {t["id"] for t in tasks}
    assert len(tasks) >= 4
    for t in tasks:
        assert {"id", "objective", "depends_on", "parallel", "components", "acceptance"} <= set(t)
        assert set(t["depends_on"]) <= ids
        assert t["id"] not in t["depends_on"]
    # a test-first task precedes its implementation task
    tests_first = [t for t in tasks if t["kind"] == "test"]
    impls = [t for t in tasks if t["kind"] == "implement"]
    assert tests_first and impls
    assert all(any(d in {x["id"] for x in tests_first} for d in t["depends_on"]) for t in impls)
    assert any(t["parallel"] for t in tasks)


@pytest.mark.req("FR-O18")
def test_design_flags_api_impact_and_new_dependencies(tmp_path: Path) -> None:
    s = settings(tmp_path)
    c = ctx(GREENFIELD, scope="greenfield")
    c.data.update(IngestAgent(s).execute(c, "ingest", 1).data_updates)
    c.outputs["decompose"] = DecomposeAgent(s).execute(c, "decompose", 1).output
    out = DesignAgent(s).execute(c, "design", 1)
    design = dict(out.artifacts)["design"]
    assert out.output["api_or_schema_impact"] is True
    assert design["api_changes"] and design["components"]
    assert design["new_dependencies"] == []
    assert design["trade_offs"] and design["risks"]


# --- delivery ----------------------------------------------------------------------------


def _prepared(tmp_path: Path, requirement: str, scope: str) -> tuple[Settings, RunContext]:
    s = settings(tmp_path)
    c = ctx(requirement, scope=scope)
    c.workspace = str(tmp_path / "ws")
    c.data.update(IngestAgent(s).execute(c, "ingest", 1).data_updates)
    dec = DecomposeAgent(s).execute(c, "decompose", 1)
    c.outputs["decompose"] = dec.output
    c.data.update(dec.data_updates)
    des = DesignAgent(s).execute(c, "design", 1)
    c.outputs["design"] = des.output
    c.data.update(des.data_updates)
    return s, c


@pytest.mark.req("FR-O18", "FR-O11")
def test_implement_writes_only_to_workspace_and_can_roll_back(tmp_path: Path) -> None:
    s, c = _prepared(tmp_path, GREENFIELD, "greenfield")
    agent = ImplementAgent(s)
    out = agent.execute(c, "implement", 1)
    receipt = out.data_updates["implement_receipt"]
    written = receipt["files_changed"]
    assert written and all((tmp_path / "ws" / p).exists() for p in written)
    assert all(not p.startswith(("/", "..")) for p in written)
    c.data.update(out.data_updates)
    result = agent.compensate(c, "implement")
    assert result["rollback"] is True
    assert not any((tmp_path / "ws" / p).exists() for p in written)


@pytest.mark.req("FR-O18")
def test_test_plan_and_docs_cover_every_acceptance_criterion(tmp_path: Path) -> None:
    s, c = _prepared(tmp_path, BROWNFIELD, "brownfield")
    plan = dict(TestPlanAgent(s).execute(c, "test_plan", 1).artifacts)["test_plan"]
    criteria = c.data["normalized"]["acceptance_criteria"]
    covered = {case["criterion"] for case in plan["cases"]}
    assert {a["id"] for a in criteria} <= covered
    assert any(case["negative"] for case in plan["cases"])
    docs = dict(DocsDraftAgent(s).execute(c, "docs_draft", 1).artifacts)["docs"]
    assert docs["text"] and "410" in docs["text"]


@pytest.mark.req("FR-O08", "FR-O18")
def test_verify_runs_real_command_and_injects_transient_faults(tmp_path: Path) -> None:
    s, c = _prepared(tmp_path, GREENFIELD, "greenfield")
    c.data.update(ImplementAgent(s).execute(c, "implement", 1).data_updates)
    flaky = Settings(**{**s.model_dump(), "demo_fault_verify_transient_failures": 2})
    agent = VerifyAgent(flaky)
    with pytest.raises(TransientStageError):
        agent.execute(c, "verify", 1)
    with pytest.raises(TransientStageError):
        agent.execute(c, "verify", 2)
    out = agent.execute(c, "verify", 3)
    assert out.output["exit_code"] == 0
    assert out.output["command"] and out.output["executed"] is True
    assert out.output["mode"] == "compile"
