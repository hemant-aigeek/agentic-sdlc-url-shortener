"""Assurance agents: security review, manual fallback, compliance check, summary.

``ComplianceCheckAgent`` is where policy enforcement meets the workflow: it
evaluates every registered policy against the run's persisted events and
artifacts, persists each evaluation with the policy version, and either lets
the run proceed, hands a blocking-but-exceptionable outcome to the
``policy_exception`` gate, or raises ``PolicyBlockedError`` so the engine
safe-stops (FR-G08, FR-O12). The decision itself is never made here — a
human owns exceptions and release readiness.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agentic_sdlc.config import Settings
from agentic_sdlc.errors import PolicyBlockedError, StageError
from agentic_sdlc.orchestration.agents.base import Agent, StageResult
from agentic_sdlc.orchestration.context import RunContext
from agentic_sdlc.orchestration.release import compute_release_decision
from agentic_sdlc.orchestration.states import StageState
from agentic_sdlc.orchestration.store import PolicyEvaluationRecord, WorkflowStore
from agentic_sdlc.policy.evaluator import PolicyInput, blocking, evaluate
from agentic_sdlc.policy.registry import (
    POLICIES,
    POLICY_VERSION,
    SECRET_PATTERNS,
    VALIDATION_FILE,
    VALIDATION_MARKERS,
)


def _latest_artifact_contents(store: WorkflowStore, run_id: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for art in store.list_artifacts(run_id):
        if getattr(art, "invalidated", False):
            continue
        out[art.kind] = art.content  # insertion order: the last one is the latest version
    return out


@dataclass
class SecurityReviewAgent(Agent):
    """Automated review of the change set and design against the security principles."""

    settings: Settings
    name: str = "security_review"

    def execute(self, ctx: RunContext, stage: str, attempt: int) -> StageResult:
        if self.settings.demo_fault_security_permanent_failure:
            raise StageError(
                "injected permanent fault (demo): automated security scanner unavailable"
            )
        change = ctx.output("implement")
        design = ctx.output("design")
        findings: list[dict[str, str]] = []
        files: dict[str, str] = {}
        receipt = ctx.data.get("implement_receipt") or {}
        workspace = ctx.workspace
        if workspace and receipt.get("files_changed"):
            for rel in receipt["files_changed"]:
                p = Path(workspace) / rel
                if p.exists():
                    files[rel] = p.read_text(encoding="utf-8")
        for rel, content in files.items():
            for name, pattern in SECRET_PATTERNS.items():
                if pattern.search(content):
                    findings.append(
                        {"severity": "HIGH", "file": rel, "finding": f"secret pattern {name}"}
                    )
            if rel.endswith(VALIDATION_FILE):
                missing = [m for m in VALIDATION_MARKERS if m not in content]
                if missing:
                    findings.append(
                        {
                            "severity": "HIGH",
                            "file": rel,
                            "finding": f"URL validation controls removed: {', '.join(missing)}",
                        }
                    )
        for dep in design.get("new_dependencies", []) if isinstance(design, dict) else []:
            findings.append(
                {"severity": "MEDIUM", "file": "design", "finding": f"new dependency {dep}"}
            )
        threat_notes = [
            "open redirect: targets are validated against scheme allow-list (FR-U02)",
            "SSRF via redirector: loopback/private/metadata targets rejected (FR-U03)",
            "approval spoofing: decisions require API key + actor header (AMB-06)",
        ]
        output = {
            "automated": True,
            "files_reviewed": sorted(files),
            "findings": findings,
            "high_findings": sum(1 for f in findings if f["severity"] == "HIGH"),
            "threat_model_notes": threat_notes,
            "change_set": change.get("change_set"),
        }
        if output["high_findings"]:
            raise StageError(
                f"security review found {output['high_findings']} HIGH finding(s): "
                + "; ".join(f["finding"] for f in findings if f["severity"] == "HIGH")
            )
        return StageResult(output=output, artifacts=[("security_review", output)])


@dataclass
class ManualSecurityReviewAgent(Agent):
    """Fallback when the automated review cannot run: produce a human checklist (never a pass)."""

    settings: Settings
    name: str = "manual_security_review"

    def execute(self, ctx: RunContext, stage: str, attempt: int) -> StageResult:
        receipt = ctx.data.get("implement_receipt") or {}
        checklist = [
            "No secret material in the change set",
            "domain/validation.py allow-list and blocked ranges untouched",
            "New routes documented in the versioned OpenAPI contract",
            "Problem responses contain no stack traces",
            "No new dependency outside the licence allow-list",
        ]
        output = {
            "automated": False,
            "manual_review_required": True,
            "files_to_review": list(receipt.get("files_changed", [])),
            "checklist": checklist,
            "residual_risk": "automated scanner did not run; a human must accept the residual "
            "risk through a policy exception (SEC-003) with a compensating control",
        }
        return StageResult(output=output, artifacts=[("security_review", output)])


@dataclass
class ComplianceCheckAgent(Agent):
    settings: Settings
    store: WorkflowStore
    name: str = "compliance_check"

    def execute(self, ctx: RunContext, stage: str, attempt: int) -> StageResult:
        run_id = ctx.run_id
        events = self.store.list_events(run_id)
        artifacts = _latest_artifact_contents(self.store, run_id)
        exceptions = self.store.list_policy_exceptions(run_id)
        inp = PolicyInput(
            ctx=ctx,
            artifacts=artifacts,
            events=events,
            exceptions=exceptions,
            forced_fail=self.settings.demo_fault_policy_fail,
            extra={"current_stage": stage},
        )
        evaluations = evaluate(inp)
        now = datetime.now(UTC)
        for ev in evaluations:
            self.store.save_policy_evaluation(
                PolicyEvaluationRecord(
                    run_id=run_id,
                    stage=stage,
                    policy_id=ev.policy_id,
                    policy_version=ev.policy_version,
                    outcome=ev.outcome.value,
                    detail=ev.detail,
                    at=now,
                )
            )
        blockers = blocking(evaluations, exceptions=exceptions, now=now)
        exceptionable = [b for b in blockers if b.exceptionable]
        hard = [b for b in blockers if not b.exceptionable]
        outcomes = {
            ev.policy_id: {"outcome": ev.outcome.value, "detail": ev.detail} for ev in evaluations
        }
        output = {
            "policy_version": POLICY_VERSION,
            "evaluated": len(evaluations),
            "outcomes": outcomes,
            "blocking": [b.policy_id for b in blockers],
            "exceptionable_blocking": [b.policy_id for b in exceptionable],
            "non_exceptionable_blocking": [b.policy_id for b in hard],
            "forced_fail": self.settings.demo_fault_policy_fail,
            "evaluated_at": now.isoformat(),
        }
        if hard:
            raise PolicyBlockedError(
                "mandatory policy failed with no admissible exception: "
                + "; ".join(f"{b.policy_id}: {b.detail}" for b in hard),
                policies=[b.policy_id for b in hard],
            )
        return StageResult(
            output=output,
            artifacts=[("compliance", output)],
            data_updates={
                "policy_blocking": [b.policy_id for b in exceptionable],
                "policy_outcomes": {k: v["outcome"] for k, v in outcomes.items()},
            },
        )


@dataclass
class SummaryAgent(Agent):
    settings: Settings
    store: WorkflowStore
    name: str = "summary"

    def execute(self, ctx: RunContext, stage: str, attempt: int) -> StageResult:
        run_id = ctx.run_id
        run = self.store.load_run(run_id)
        if run is None:
            raise StageError("run not found")
        stages = self.store.load_stages(run_id)
        evaluations = self.store.list_policy_evaluations(run_id)
        exceptions = self.store.list_policy_exceptions(run_id)
        events = self.store.list_events(run_id)
        mandatory = {p.id: p.mandatory for p in POLICIES}
        release = compute_release_decision(
            run_state=run.state,
            stage_states={n: s.state for n, s in stages.items()},
            evaluations=evaluations,
            exceptions=exceptions,
            mandatory=mandatory,
        )
        normalized = ctx.data.get("normalized", {})
        retries = sum(1 for e in events if e.kind.value == "retry_scheduled")
        fallbacks = [n for n, s in stages.items() if s.state is StageState.FALLBACK]
        verify = ctx.output("verify")
        summary = {
            "title": ctx.title,
            "run_id": run_id,
            "scope": ctx.data.get("scope", ctx.scope),
            "requirement_version": ctx.requirement_version,
            "graph_version": ctx.graph_version,
            "policy_version": ctx.policy_version,
            "release_decision": release["decision"],
            "release_evidence": release,
            "plan_and_rationale": {
                "statements": normalized.get("functional_statements", []),
                "acceptance_criteria": [c["id"] for c in normalized.get("acceptance_criteria", [])],
                "decomposition_tasks": len(ctx.data.get("decomposition_tasks", [])),
                "design_api_impact": ctx.output("design").get("api_or_schema_impact"),
                "clarifications": ctx.data.get("clarifications", []),
                "quality_reason": ctx.data.get("quality_reason"),
            },
            "artifacts": {kind: ref.to_dict() for kind, ref in ctx.artifacts.items()},
            "validation": {
                "verify_command": verify.get("command"),
                "verify_exit_code": verify.get("exit_code"),
                "verify_executed": verify.get("executed", False),
                "retries": retries,
                "fallback_stages": fallbacks,
            },
            "decisions": ctx.decisions,
            "assumptions": ctx.assumptions,
            "risks_and_trade_offs": {
                "accepted_exceptions": release["accepted_exceptions"],
                "security_findings": ctx.output("security_review").get("findings", []),
                "manual_security_review": not ctx.output("security_review").get("automated", True),
            },
            "limitations": [
                "deterministic agents: implementation output is a red-test scaffold plus change "
                "plan, promoted by a human (ADR-010)",
                "measurements are demonstration data from a single local process",
            ],
            "measurement_type": "demonstration",
        }
        return StageResult(
            output={"release_decision": release["decision"], "retries": retries},
            artifacts=[("engineering_summary", summary)],
            data_updates={"release_decision": release["decision"]},
        )
