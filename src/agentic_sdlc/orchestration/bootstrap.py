"""Default wiring of agents and planners for the control plane.

Kept separate from the engine so the API factory, the CLI and the tests
assemble the same system the same way.
"""

from __future__ import annotations

from agentic_sdlc.config import Settings
from agentic_sdlc.orchestration import planner
from agentic_sdlc.orchestration.agents import sdlc
from agentic_sdlc.orchestration.agents.base import AgentRegistry
from agentic_sdlc.orchestration.engine import Planner


def default_agents(settings: Settings) -> AgentRegistry:
    registry = AgentRegistry()
    sdlc.register_all(registry, settings)
    return registry


def default_planners() -> dict[str, Planner]:
    return {"sdlc": planner.build_graph}
