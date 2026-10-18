"""SDLC graph planner (FR-O02..O04, FR-O14; ADR-005, ADR-009).

``build_graph`` is a pure function of the run context, so the engine can
rebuild it at any time and ``WorkflowGraph.diff`` tells it exactly what a
replan changed. Only facts that change *through a governed decision* shape
the structure (initial scope, recorded clarifications); facts discovered by
agents at run time (classified scope, ambiguity verdict, policy outcomes)
select branches through conditions, which are evaluated when a stage becomes
ready. That split is what keeps "the graph" stable between loads while still
letting the path differ per scenario.

Shape (see plan §3):

    ingest → quality_check →(needs clarification)→ clarification [H] →(replan: requirement_revision)
           →(brownfield)→ impact_analysis → decompose → design → design_approval [H]
           → {implement ∥ test_plan ∥ docs_draft} → verify (retry) → security_review (fallback)
           → compliance_check →(blocking)→ policy_exception [H] → release_readiness [H] → summary
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from agentic_sdlc.config import Settings
from agentic_sdlc.orchestration.context import RunContext
from agentic_sdlc.orchestration.graph import StageSpec, WorkflowGraph
from agentic_sdlc.orchestration.policies import NO_RETRY, GatePolicy, RetryPolicy, TimeoutPolicy

HUMAN = "human"


# --- conditions (named so the graph signature and the audit trail can cite them) -------


def needs_clarification(m: Mapping[str, Any]) -> bool:
    return m.get("clarification_required") is True


def is_brownfield(m: Mapping[str, Any]) -> bool:
    return m.get("scope") == "brownfield"


def policy_blocking(m: Mapping[str, Any]) -> bool:
    return bool(m.get("policy_blocking"))


def make_planner(settings: Settings) -> Callable[[RunContext], WorkflowGraph]:
    retry = RetryPolicy(
        max_attempts=settings.retry_max_attempts,
        base_delay_s=settings.retry_base_delay_s,
        multiplier=settings.retry_multiplier,
        max_delay_s=settings.retry_max_delay_s,
    )
    timeout = TimeoutPolicy(settings.stage_timeout_s)
    gate = GatePolicy(timeout_s=settings.gate_timeout_s)

    def build_graph(ctx: RunContext) -> WorkflowGraph:
        clarified = bool(ctx.data.get("clarifications"))
        explicit_greenfield = ctx.scope == "greenfield"
        specs: list[StageSpec] = [
            StageSpec(
                "ingest",
                "ingest",
                retry=NO_RETRY,
                timeout=timeout,
                purpose="normalise the requirement and classify its scope",
                emits=("normalized_requirement",),
            ),
            StageSpec(
                "quality_check",
                "quality_check",
                depends_on=("ingest",),
                retry=NO_RETRY,
                timeout=timeout,
                purpose="completeness/consistency/testability/boundary checks; ambiguity detection",
                emits=("quality_check",),
            ),
            StageSpec(
                "clarification",
                HUMAN,
                depends_on=("quality_check",),
                owner=HUMAN,
                gate_kind="clarification",
                gate=gate,
                condition=needs_clarification,
                condition_label="quality_check.clarification_required",
                purpose="human resolves material ambiguity before any design or implementation",
            ),
        ]
        head = "clarification"
        if clarified:
            specs.append(
                StageSpec(
                    "requirement_revision",
                    "requirement_revision",
                    depends_on=("clarification",),
                    retry=NO_RETRY,
                    timeout=timeout,
                    purpose="fold the recorded clarification into requirement v{n+1}",
                    emits=("normalized_requirement", "requirement_revision"),
                )
            )
            head = "requirement_revision"
        decompose_deps: tuple[str, ...] = (head,)
        if not explicit_greenfield:
            specs.append(
                StageSpec(
                    "impact_analysis",
                    "impact_analysis",
                    depends_on=(head,),
                    retry=NO_RETRY,
                    timeout=TimeoutPolicy(max(settings.stage_timeout_s, 30.0)),
                    condition=is_brownfield,
                    condition_label="scope == brownfield",
                    purpose="brownfield impact analysis before any change",
                    emits=("impact_analysis",),
                )
            )
            decompose_deps = ("impact_analysis",)
        specs += [
            StageSpec(
                "decompose",
                "decompose",
                depends_on=decompose_deps,
                retry=NO_RETRY,
                timeout=timeout,
                purpose="dependency-aware task decomposition",
                emits=("decomposition",),
            ),
            StageSpec(
                "design",
                "design",
                depends_on=("decompose",),
                retry=NO_RETRY,
                timeout=timeout,
                purpose="components, API/schema impact, trade-offs, risks",
                emits=("design",),
            ),
            StageSpec(
                "design_approval",
                HUMAN,
                depends_on=("design",),
                owner=HUMAN,
                gate=gate,
                purpose="architecture approval; API/schema changes must be acknowledged (CHG-002)",
            ),
            StageSpec(
                "implement",
                "implement",
                depends_on=("design_approval",),
                retry=NO_RETRY,
                timeout=timeout,
                compensable=True,
                purpose="apply the change set to the run workspace (reversible)",
                emits=("change_set",),
            ),
            StageSpec(
                "test_plan",
                "test_plan",
                depends_on=("design_approval",),
                retry=NO_RETRY,
                timeout=timeout,
                purpose="test matrix with negative cases per acceptance criterion",
                emits=("test_plan",),
            ),
            StageSpec(
                "docs_draft",
                "docs_draft",
                depends_on=("design_approval",),
                retry=NO_RETRY,
                timeout=timeout,
                purpose="documentation draft for the change",
                emits=("docs",),
            ),
            StageSpec(
                "verify",
                "verify",
                depends_on=("implement", "test_plan", "docs_draft"),
                retry=retry,
                timeout=TimeoutPolicy(settings.verify_timeout_s + 5.0),
                purpose="execute the impacted regression targets / compile the change set",
                emits=("verification",),
            ),
            StageSpec(
                "security_review",
                "security_review",
                depends_on=("verify",),
                retry=NO_RETRY,
                timeout=timeout,
                fallback="manual_security_review",
                purpose="automated security review; falls back to a manual checklist",
                emits=("security_review",),
            ),
            StageSpec(
                "compliance_check",
                "compliance_check",
                # after security_review on purpose: SEC-003 must see the review's outcome
                # (automated vs fallback) and CMP-001 must not observe an in-flight sibling
                depends_on=("verify", "security_review"),
                retry=NO_RETRY,
                timeout=timeout,
                purpose="evaluate every versioned policy; block or raise an exception gate",
                emits=("compliance",),
            ),
            StageSpec(
                "policy_exception",
                HUMAN,
                depends_on=("compliance_check",),
                owner=HUMAN,
                gate=gate,
                condition=policy_blocking,
                condition_label="compliance_check.blocking non-empty",
                purpose="human accepts a scoped, expiring policy exception + compensating control",
            ),
            StageSpec(
                "release_readiness",
                HUMAN,
                depends_on=("policy_exception",),
                owner=HUMAN,
                gate=gate,
                purpose="human release-readiness decision on the computed evidence",
            ),
            StageSpec(
                "summary",
                "summary",
                depends_on=("release_readiness",),
                retry=NO_RETRY,
                timeout=timeout,
                purpose="final engineering summary with release decision and evidence index",
                emits=("engineering_summary",),
            ),
        ]
        return WorkflowGraph.build(specs)

    return build_graph


def build_graph(ctx: RunContext) -> WorkflowGraph:
    """Default planner with default settings (used when no settings are supplied)."""
    return make_planner(Settings())(ctx)
