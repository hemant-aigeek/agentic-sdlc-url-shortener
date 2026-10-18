"""The Agent protocol (ADR-010).

An agent owns exactly one kind of stage work. It receives the run context
(read-only by convention), does its work, and returns a ``StageResult``; it
never touches workflow state, never transitions a gate, and never writes to
the live repository — the engine owns all of that. Failures are reported by
raising ``StageError`` with an explicit transient/permanent classification so
the engine can apply the stage's retry policy (FR-O08).

Agents are deterministic for the assessment (Gate 3, AMB-08). An LLM-backed
agent would implement this same interface; see BACKLOG.md.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from agentic_sdlc.orchestration.context import RunContext


@dataclass
class StageResult:
    output: dict[str, Any] = field(default_factory=dict)
    artifacts: list[tuple[str, dict[str, Any]]] = field(default_factory=list)  # (kind, content)
    assumptions: list[dict[str, Any]] = field(default_factory=list)
    data_updates: dict[str, Any] = field(default_factory=dict)  # merged into ctx.data


class Agent(ABC):
    name: str = "agent"

    @abstractmethod
    def execute(self, ctx: RunContext, stage: str, attempt: int) -> StageResult: ...

    def compensate(self, ctx: RunContext, stage: str) -> dict[str, Any]:
        """Undo or counteract this stage's side effects. Default: nothing to do."""
        return {"compensated": False, "reason": "stage has no side effects"}


class AgentRegistry:
    def __init__(self, agents: dict[str, Agent] | None = None) -> None:
        self._agents: dict[str, Agent] = dict(agents or {})

    def register(self, key: str, agent: Agent) -> None:
        self._agents[key] = agent

    def get(self, key: str) -> Agent:
        try:
            return self._agents[key]
        except KeyError as exc:
            raise KeyError(f"no agent registered for {key!r}") from exc

    def __contains__(self, key: str) -> bool:
        return key in self._agents
