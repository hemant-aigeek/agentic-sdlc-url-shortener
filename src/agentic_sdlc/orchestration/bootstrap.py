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
from agentic_sdlc.orchestration.store import WorkflowStore


def default_agents(settings: Settings, store: WorkflowStore) -> AgentRegistry:
    registry = AgentRegistry()
    sdlc.register_all(registry, settings, store)
    return registry


def default_planners(settings: Settings | None = None) -> dict[str, Planner]:
    return {"sdlc": planner.make_planner(settings or Settings())}
