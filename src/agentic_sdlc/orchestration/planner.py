"""SDLC graph planner — builds the per-run dependency graph from the run context.

The full planner (conditional clarification and impact-analysis branches,
fan-out/join groups, human gates, policy-exception gate) is implemented in
task group G7. Until then the control plane refuses to plan rather than
pretending to.
"""

from __future__ import annotations

from agentic_sdlc.orchestration.context import RunContext
from agentic_sdlc.orchestration.graph import WorkflowGraph


def build_graph(ctx: RunContext) -> WorkflowGraph:
    raise NotImplementedError("the SDLC planner is implemented in task group G7")
