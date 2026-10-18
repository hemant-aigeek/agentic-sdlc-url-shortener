"""Registration of the SDLC stage agents (ADR-010).

Keys are the ``StageSpec.agent`` names used by the planner. Human-owned
stages (gates) use the ``human`` key, which is a sentinel: the engine never
executes it, and asking for it fails loudly.
"""

from __future__ import annotations

from agentic_sdlc.config import Settings
from agentic_sdlc.errors import StageError
from agentic_sdlc.orchestration.agents.analysis import (
    DecomposeAgent,
    DesignAgent,
    ImpactAnalysisAgent,
)
from agentic_sdlc.orchestration.agents.assurance import (
    ComplianceCheckAgent,
    ManualSecurityReviewAgent,
    SecurityReviewAgent,
    SummaryAgent,
)
from agentic_sdlc.orchestration.agents.base import Agent, AgentRegistry, StageResult
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
from agentic_sdlc.orchestration.store import WorkflowStore

HUMAN = "human"


class HumanSentinel(Agent):
    name = HUMAN

    def execute(self, ctx: RunContext, stage: str, attempt: int) -> StageResult:
        raise StageError(f"stage {stage!r} is human-owned and cannot be executed by an agent")


def register_all(registry: AgentRegistry, settings: Settings, store: WorkflowStore) -> None:
    registry.register("ingest", IngestAgent(settings))
    registry.register("quality_check", QualityCheckAgent(settings))
    registry.register("requirement_revision", RequirementRevisionAgent(settings))
    registry.register("impact_analysis", ImpactAnalysisAgent(settings))
    registry.register("decompose", DecomposeAgent(settings))
    registry.register("design", DesignAgent(settings))
    registry.register("implement", ImplementAgent(settings))
    registry.register("test_plan", TestPlanAgent(settings))
    registry.register("docs_draft", DocsDraftAgent(settings))
    registry.register("verify", VerifyAgent(settings))
    registry.register("security_review", SecurityReviewAgent(settings))
    registry.register("manual_security_review", ManualSecurityReviewAgent(settings))
    registry.register("compliance_check", ComplianceCheckAgent(settings, store))
    registry.register("summary", SummaryAgent(settings, store))
    registry.register(HUMAN, HumanSentinel())
