"""RunContext — cross-stage context and decision lineage (FR-O06, FR-O07).

Agents read the context and return results; only the engine mutates it, and
every mutation is persisted with the run. ``as_mapping()`` is what graph
conditions see, so a condition can only branch on recorded state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ArtifactRef:
    id: int
    kind: str
    version: int
    stage: str

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "version": self.version, "stage": self.stage}


@dataclass
class RunContext:
    run_id: str
    title: str
    scope: str  # greenfield | brownfield | ambiguous
    requirement_raw: str
    requirement_version: int = 1
    policy_version: str = "0.0.0"
    graph_version: int = 1
    planner: str = "sdlc"
    workspace: str | None = None
    data: dict[str, Any] = field(
        default_factory=dict
    )  # normalised requirement, flags, clarifications
    outputs: dict[str, dict[str, Any]] = field(default_factory=dict)  # stage -> output
    artifacts: dict[str, ArtifactRef] = field(default_factory=dict)  # kind -> latest ref
    decisions: list[dict[str, Any]] = field(default_factory=list)
    assumptions: list[dict[str, Any]] = field(default_factory=list)

    # --- views ---------------------------------------------------------------

    def as_mapping(self) -> dict[str, Any]:
        """Flat view for graph conditions and agents."""
        return {
            "run_id": self.run_id,
            "scope": self.scope,
            "requirement_version": self.requirement_version,
            "graph_version": self.graph_version,
            **self.data,
            "outputs": self.outputs,
            "decisions": self.decisions,
        }

    def output(self, stage: str) -> dict[str, Any]:
        return self.outputs.get(stage, {})

    # --- persistence ---------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "title": self.title,
            "scope": self.scope,
            "requirement_raw": self.requirement_raw,
            "requirement_version": self.requirement_version,
            "policy_version": self.policy_version,
            "graph_version": self.graph_version,
            "planner": self.planner,
            "workspace": self.workspace,
            "data": self.data,
            "outputs": self.outputs,
            "artifacts": {k: v.to_dict() for k, v in self.artifacts.items()},
            "decisions": self.decisions,
            "assumptions": self.assumptions,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RunContext:
        return cls(
            run_id=d["run_id"],
            title=d["title"],
            scope=d["scope"],
            requirement_raw=d["requirement_raw"],
            requirement_version=d.get("requirement_version", 1),
            policy_version=d.get("policy_version", "0.0.0"),
            graph_version=d.get("graph_version", 1),
            planner=d.get("planner", "sdlc"),
            workspace=d.get("workspace"),
            data=dict(d.get("data", {})),
            outputs={k: dict(v) for k, v in d.get("outputs", {}).items()},
            artifacts={k: ArtifactRef(**v) for k, v in d.get("artifacts", {}).items()},
            decisions=list(d.get("decisions", [])),
            assumptions=list(d.get("assumptions", [])),
        )
