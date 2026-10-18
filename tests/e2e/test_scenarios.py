"""The three assessment scenarios executed end-to-end through the real engine,
agents, planner and policies (SCN-A/B/C; SC-02, SC-04, SC-05, SC-06).

Only the store is in-memory; everything else is the production wiring. Human
decisions are made explicitly by the test — nothing advances past a gate on
its own.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from agentic_sdlc.config import Settings
from agentic_sdlc.orchestration.bootstrap import default_agents, default_planners
from agentic_sdlc.orchestration.engine import Engine
from agentic_sdlc.orchestration.events import EventKind
from agentic_sdlc.orchestration.release import (
    NOT_READY,
    READY,
    READY_WITH_LIMITATIONS,
    compute_release_decision,
)
from agentic_sdlc.orchestration.states import RunState
from agentic_sdlc.persistence.db import Database
from agentic_sdlc.persistence.workflow_store import SqlWorkflowStore
from agentic_sdlc.policy.registry import POLICIES, POLICY_VERSION

REPO_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.e2e

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
HUMAN = "hemant"


@pytest.fixture
def store() -> Iterator[SqlWorkflowStore]:
    db = Database("sqlite+pysqlite:///:memory:")
    db.create_all()
    yield SqlWorkflowStore(db)
    db.dispose()


def make_settings(tmp_path: Path, **overrides: Any) -> Settings:
    base = dict(
        data_dir=tmp_path / "data",
        repository_root=REPO_ROOT,
        verify_mode="compile",
        retry_base_delay_s=0.01,
        retry_max_delay_s=0.02,
        stage_timeout_s=30.0,
        gate_timeout_s=None,
        log_json=False,
    )
    base.update(overrides)
    return Settings(**base)


def make_engine(store: SqlWorkflowStore, settings: Settings) -> Engine:
    return Engine(
        store=store,
        agents=default_agents(settings, store),
        planners=default_planners(settings),
        settings=settings,
        policy_version=POLICY_VERSION,
    )


def states(engine: Engine, run_id: str) -> dict[str, str]:
    return {s["name"]: s.get("state", "PENDING") for s in engine.graph_view(run_id)["stages"]}


def kinds(store: SqlWorkflowStore, run_id: str, kind: EventKind, stage: str | None = None) -> int:
    return sum(
        1
        for e in store.list_events(run_id)
        if e.kind is kind and (stage is None or e.stage == stage)
    )


def release_decision(store: SqlWorkflowStore, run_id: str) -> dict[str, Any]:
    run = store.load_run(run_id)
    assert run is not None
    return compute_release_decision(
        run_state=run.state,
        stage_states={n: s.state for n, s in store.load_stages(run_id).items()},
        evaluations=store.list_policy_evaluations(run_id),
        exceptions=store.list_policy_exceptions(run_id),
        mandatory={p.id: p.mandatory for p in POLICIES},
    )


def approve(engine: Engine, run_id: str, gate: str, **payload: Any) -> None:
    engine.decide(
        run_id,
        gate=gate,
        actor=HUMAN,
        decision="approve",
        reason=f"approved {gate}",
        payload=payload,
    )
    engine.run(run_id)


# --- SCN-A: greenfield -------------------------------------------------------------------


@pytest.mark.req("SCN-A", "FR-O03", "FR-O08", "SC-04", "SC-05")
def test_greenfield_proceeds_without_clarification_with_parallel_fanout_and_retry(
    store: SqlWorkflowStore, tmp_path: Path
) -> None:
    engine = make_engine(store, make_settings(tmp_path, demo_fault_verify_transient_failures=2))
    run_id = engine.start(title="analytics summary", requirement=GREENFIELD, scope="greenfield")
    run = engine.run(run_id)

    # straight through to the architecture gate; clarification skipped with a recorded reason
    assert run.state is RunState.WAITING_APPROVAL
    st = states(engine, run_id)
    assert st["clarification"] == "SKIPPED" and "impact_analysis" not in st
    quality = engine.load(run_id).context.output("quality_check")
    assert quality["clarification_required"] is False
    assert "no clarification" in quality["reason_no_clarification"]
    assert st["design_approval"] == "READY" and st["implement"] == "PENDING"

    approve(engine, run_id, "design_approval", api_change_acknowledged=True)
    run = engine.load(run_id)
    assert run.state is RunState.WAITING_APPROVAL
    st = states(engine, run_id)
    # fan-out executed as one parallel batch, join waited for all three
    assert {st["implement"], st["test_plan"], st["docs_draft"]} == {"SUCCEEDED"}
    groups = {s["name"]: s["parallel_group"] for s in engine.graph_view(run_id)["stages"]}
    assert groups["implement"] == groups["test_plan"] == groups["docs_draft"]
    stages = store.load_stages(run_id)
    fanout = [stages[n] for n in ("implement", "test_plan", "docs_draft")]
    assert all(s.started_at and s.ended_at for s in fanout)
    assert stages["verify"].started_at >= max(s.ended_at for s in fanout)  # type: ignore[type-var]
    # bounded retry: two injected transient failures, third attempt succeeded
    assert st["verify"] == "SUCCEEDED" and stages["verify"].attempt == 3
    assert kinds(store, run_id, EventKind.RETRY_SCHEDULED, "verify") == 2
    assert kinds(store, run_id, EventKind.RECOVERY_COMPLETED, "verify") == 1
    assert st["policy_exception"] == "SKIPPED"  # nothing blocked
    assert st["release_readiness"] == "READY"

    approve(engine, run_id, "release_readiness")
    run = engine.load(run_id)
    assert run.state is RunState.COMPLETED
    summary = [a for a in store.list_artifacts(run_id) if a.kind == "engineering_summary"][-1]
    assert summary.content["release_decision"] == READY
    assert summary.content["validation"]["retries"] == 2
    assert release_decision(store, run_id)["decision"] == READY
    # every gate that opened has a recorded human decision (SC-05)
    opened = {e.stage for e in store.list_events(run_id) if e.kind is EventKind.GATE_OPENED}
    decided = {d.gate for d in store.list_decisions(run_id)}
    assert opened == decided == {"design_approval", "release_readiness"}


# --- SCN-B: brownfield -------------------------------------------------------------------


@pytest.mark.req("SCN-B", "FR-O17", "FR-G07", "NFR-10")
def test_brownfield_runs_impact_analysis_before_any_change(
    store: SqlWorkflowStore, tmp_path: Path
) -> None:
    engine = make_engine(store, make_settings(tmp_path))
    run_id = engine.start(title="410 for expired", requirement=BROWNFIELD, scope="brownfield")
    assert engine.run(run_id).state is RunState.WAITING_APPROVAL
    st = states(engine, run_id)
    assert st["impact_analysis"] == "SUCCEEDED" and st["implement"] == "PENDING"
    impact = [a for a in store.list_artifacts(run_id) if a.kind == "impact_analysis"][-1].content
    assert "src/agentic_sdlc/domain/service.py" in impact["impacted_modules"]
    assert impact["impacted_tests"] and impact["regression_risks"]
    design = engine.load(run_id).context.output("design")
    assert design["api_or_schema_impact"] is True  # status-code change is a contract change

    approve(engine, run_id, "design_approval", api_change_acknowledged=True)
    approve(engine, run_id, "release_readiness")
    assert engine.load(run_id).state is RunState.COMPLETED
    outcomes = {p.policy_id: p.outcome for p in store.list_policy_evaluations(run_id)}
    assert outcomes["CHG-001"] == "PASS" and outcomes["CHG-002"] == "PASS"
    assert all(p.policy_version == POLICY_VERSION for p in store.list_policy_evaluations(run_id))
    events = store.list_events(run_id)
    impact_done = next(
        e.seq
        for e in events
        if e.kind is EventKind.STAGE_SUCCEEDED and e.stage == "impact_analysis"
    )
    impl_started = next(
        e.seq for e in events if e.kind is EventKind.STAGE_STARTED and e.stage == "implement"
    )
    assert impact_done < impl_started
    verify = engine.load(run_id).context.output("verify")
    assert verify["executed"] is True and verify["exit_code"] == 0
    assert release_decision(store, run_id)["decision"] == READY


# --- SCN-C: ambiguous -----------------------------------------------------------------------


@pytest.mark.req("SCN-C", "FR-O14", "FR-O10", "FR-G09", "FR-G04")
def test_ambiguous_requirement_blocks_clarifies_replans_and_accepts_exception(
    store: SqlWorkflowStore, tmp_path: Path
) -> None:
    engine = make_engine(store, make_settings(tmp_path, demo_fault_security_permanent_failure=True))
    run_id = engine.start(title="expiry + reuse", requirement=AMBIGUOUS, scope="auto")
    run = engine.run(run_id)

    # 1. detected, blocked, waiting for a human
    assert run.state is RunState.WAITING_CLARIFICATION
    st = states(engine, run_id)
    assert st["clarification"] == "READY" and st["decompose"] == "PENDING"
    assert st["implement"] == "PENDING"
    gate = engine.open_gates(run_id)[0]
    assert gate["kind"] == "clarification" and "clarify" in gate["options"]
    ambiguities = gate["context"]["upstream_outputs"]["quality_check"]["ambiguities"]
    assert {a["kind"] for a in ambiguities} >= {"undefined_quantity", "conflict"}
    # ticking without a decision changes nothing
    assert engine.run(run_id).state is RunState.WAITING_CLARIFICATION

    # 2. human clarifies -> requirement v2, replan, resume at the right stage
    answers = {a["id"]: a["options"][0]["id"] for a in ambiguities}
    engine.decide(
        run_id,
        gate="clarification",
        actor=HUMAN,
        decision="clarify",
        reason="expire 30 days after creation; codes are never reused",
        payload={"answers": answers},
    )
    run = engine.load(run_id)
    assert run.requirement_version == 2 and run.graph_version == 2
    replans = store.list_replans(run_id)
    assert len(replans) == 1
    assert "requirement_revision" not in {s["name"] for s in replans[0].graph_before["stages"]}
    assert "requirement_revision" in {s["name"] for s in replans[0].graph_after["stages"]}
    assert "decompose" in replans[0].invalidated
    assert engine.run(run_id).state is RunState.WAITING_APPROVAL
    st = states(engine, run_id)
    assert st["requirement_revision"] == "SUCCEEDED" and st["ingest"] == "SUCCEEDED"
    assert store.load_stages(run_id)["ingest"].attempt == 1  # unaffected stage not re-run
    norm = engine.load(run_id).context.data["normalized"]
    assert norm["version"] == 2 and norm["resolved_ambiguities"]

    # 3. design approval, then the automated security review fails permanently -> fallback
    approve(engine, run_id, "design_approval", api_change_acknowledged=True)
    run = engine.load(run_id)
    st = states(engine, run_id)
    assert st["security_review"] == "FALLBACK"
    assert kinds(store, run_id, EventKind.FALLBACK_USED, "security_review") == 1
    assert kinds(store, run_id, EventKind.RETRY_SCHEDULED, "security_review") == 0  # permanent
    # 4. SEC-003 asks for an exception -> the policy_exception gate opens
    assert run.state is RunState.WAITING_APPROVAL and st["policy_exception"] == "READY"
    outcomes = {p.policy_id: p.outcome for p in store.list_policy_evaluations(run_id)}
    assert outcomes["SEC-003"] == "EXCEPTION-REQUESTED"
    assert release_decision(store, run_id)["decision"] == NOT_READY

    # 5. human accepts a scoped, expiring exception with a compensating control
    approve(
        engine,
        run_id,
        "policy_exception",
        compensating_control="manual security checklist completed and attached",
        scope="this run only",
    )
    exceptions = store.list_policy_exceptions(run_id)
    assert [e.policy_id for e in exceptions] == ["SEC-003"]
    assert exceptions[0].status == "approved" and exceptions[0].expires_at is not None
    assert states(engine, run_id)["release_readiness"] == "READY"
    approve(engine, run_id, "release_readiness")
    assert engine.load(run_id).state is RunState.COMPLETED
    assert release_decision(store, run_id)["decision"] == READY_WITH_LIMITATIONS
    summary = [a for a in store.list_artifacts(run_id) if a.kind == "engineering_summary"][-1]
    assert summary.content["release_decision"] == READY_WITH_LIMITATIONS
    assert summary.content["risks_and_trade_offs"]["manual_security_review"] is True
    # lineage: the summary derives (transitively) from the v2 requirement
    assert any(
        a.kind == "normalized_requirement" and a.version == 2 for a in store.list_artifacts(run_id)
    )


# --- additional executed demonstrations ----------------------------------------------------


@pytest.mark.req("FR-G05", "FR-O11", "SC-04")
def test_rejection_at_release_rolls_back_the_change_set(
    store: SqlWorkflowStore, tmp_path: Path
) -> None:
    engine = make_engine(store, make_settings(tmp_path))
    run_id = engine.start(title="g", requirement=GREENFIELD, scope="greenfield")
    engine.run(run_id)
    approve(engine, run_id, "design_approval", api_change_acknowledged=True)
    ctx = engine.load(run_id).context
    written = [
        Path(ctx.workspace or "") / p for p in ctx.data["implement_receipt"]["files_changed"]
    ]
    assert written and all(p.exists() for p in written)
    engine.decide(
        run_id, gate="release_readiness", actor=HUMAN, decision="reject", reason="not this sprint"
    )
    run = engine.load(run_id)
    assert run.state is RunState.REJECTED
    assert states(engine, run_id)["implement"] == "COMPENSATED"
    assert kinds(store, run_id, EventKind.ROLLBACK_COMPLETED, "implement") == 1
    assert not any(p.exists() for p in written)
    assert states(engine, run_id)["summary"] == "PENDING"  # nothing ran after the rejection


@pytest.mark.req("FR-O13", "NFR-03")
def test_restart_mid_run_resumes_from_persisted_state(
    store: SqlWorkflowStore, tmp_path: Path
) -> None:
    settings = make_settings(tmp_path)
    first = make_engine(store, settings)
    run_id = first.start(title="g", requirement=GREENFIELD, scope="greenfield")
    assert first.run(run_id, max_batches=1).state is RunState.SUSPENDED
    done_before = {n for n, s in states(first, run_id).items() if s == "SUCCEEDED"}
    assert done_before == {"ingest"}
    second = make_engine(store, settings)  # a fresh process over the same store
    assert second.resume(run_id).state is RunState.WAITING_APPROVAL
    assert kinds(store, run_id, EventKind.RUN_RESUMED) == 1
    assert store.load_stages(run_id)["ingest"].attempt == 1


@pytest.mark.req("FR-G08", "FR-O12", "SC-06")
def test_failed_mandatory_policy_safe_stops_and_release_is_not_ready(
    store: SqlWorkflowStore, tmp_path: Path
) -> None:
    engine = make_engine(store, make_settings(tmp_path, demo_fault_policy_fail="SEC-002"))
    run_id = engine.start(title="g", requirement=GREENFIELD, scope="greenfield")
    engine.run(run_id)
    approve(engine, run_id, "design_approval", api_change_acknowledged=True)
    run = engine.load(run_id)
    assert run.state is RunState.SAFE_STOPPED
    assert run.terminal_reason and run.terminal_reason.startswith("POLICY_BLOCKED")
    st = states(engine, run_id)
    assert st["compliance_check"] == "FAILED" and st["release_readiness"] == "PENDING"
    decision = release_decision(store, run_id)
    assert decision["decision"] == NOT_READY and "SEC-002" in decision["blocking_policies"]
    assert kinds(store, run_id, EventKind.SAFE_STOP) == 1


@pytest.mark.req("FR-G05", "FR-O14")
def test_design_rejection_with_return_to_reworks_instead_of_ending(
    store: SqlWorkflowStore, tmp_path: Path
) -> None:
    engine = make_engine(store, make_settings(tmp_path))
    run_id = engine.start(title="g", requirement=GREENFIELD, scope="greenfield")
    engine.run(run_id)
    engine.decide(
        run_id,
        gate="design_approval",
        actor=HUMAN,
        decision="reject",
        reason="split the endpoint",
        payload={"return_to": "decompose"},
    )
    run = engine.load(run_id)
    assert run.state is RunState.RUNNING and run.graph_version == 2
    assert kinds(store, run_id, EventKind.REPLAN) == 1
    assert engine.run(run_id).state is RunState.WAITING_APPROVAL
    assert store.load_stages(run_id)["decompose"].attempt == 1  # re-run from a clean state
    assert len([d for d in store.list_decisions(run_id) if d.gate == "design_approval"]) == 1
    assert states(engine, run_id)["design_approval"] == "READY"  # the gate re-armed
