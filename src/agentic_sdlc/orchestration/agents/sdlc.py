"""Registration of the SDLC stage agents (filled in task group G7)."""

from __future__ import annotations

from agentic_sdlc.config import Settings
from agentic_sdlc.orchestration.agents.base import AgentRegistry


def register_all(registry: AgentRegistry, settings: Settings) -> None:
    """Register every SDLC agent. No agents exist before G7; the registry stays empty."""
    _ = settings
    _ = registry
