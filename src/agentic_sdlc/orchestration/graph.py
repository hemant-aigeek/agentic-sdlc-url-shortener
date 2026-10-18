"""The workflow dependency graph (FR-O02..O04, FR-O14; ADR-005, ADR-009).

A ``WorkflowGraph`` is data: stages, hard edges, and conditions. It knows how
to validate itself, compute the ready set from a map of stage states, walk the
downstream closure of a change, and diff against a rebuilt graph. It does not
execute anything — that is the engine's job — which keeps the structure
inspectable from tests, the API and the evidence export.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from agentic_sdlc.orchestration.policies import GatePolicy, RetryPolicy, TimeoutPolicy
from agentic_sdlc.orchestration.states import StageState

Condition = Callable[[Mapping[str, Any]], bool]


class GraphError(ValueError):
    pass


@dataclass(frozen=True)
class StageSpec:
    name: str
    agent: str
    depends_on: tuple[str, ...] = ()
    owner: str = "agent"  # "agent" | "human"
    condition: Condition | None = None
    condition_label: str | None = None
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    timeout: TimeoutPolicy = field(default_factory=TimeoutPolicy)
    fallback: str | None = None  # agent key executed when retries are exhausted
    compensable: bool = False  # stage registers an inverse action
    gate: GatePolicy = field(default_factory=GatePolicy)
    gate_kind: str = "approval"  # "approval" | "clarification" (human-owned stages only)
    purpose: str = ""
    emits: tuple[str, ...] = ()  # artifact kinds produced
    retry_max_attempts: int | None = None  # convenience override used by tests/planner

    def __post_init__(self) -> None:
        if self.owner not in {"agent", "human"}:
            raise GraphError(f"stage {self.name!r}: owner must be 'agent' or 'human'")
        if self.gate_kind not in {"approval", "clarification"}:
            raise GraphError(f"stage {self.name!r}: unknown gate_kind {self.gate_kind!r}")
        if self.retry_max_attempts is not None:
            object.__setattr__(
                self,
                "retry",
                RetryPolicy(
                    max_attempts=self.retry_max_attempts,
                    base_delay_s=self.retry.base_delay_s,
                    multiplier=self.retry.multiplier,
                    max_delay_s=self.retry.max_delay_s,
                ),
            )

    @property
    def is_gate(self) -> bool:
        return self.owner == "human"

    @property
    def is_conditional(self) -> bool:
        return self.condition is not None

    def signature(self) -> dict[str, Any]:
        """Structural identity used by ``diff``; callables are compared by label."""
        return {
            "agent": self.agent,
            "depends_on": list(self.depends_on),
            "owner": self.owner,
            "condition": self.condition_label
            or (self.condition.__name__ if self.condition else None),
            "retry": {
                "max_attempts": self.retry.max_attempts,
                "base_delay_s": self.retry.base_delay_s,
                "multiplier": self.retry.multiplier,
                "max_delay_s": self.retry.max_delay_s,
            },
            "timeout_s": self.timeout.seconds,
            "fallback": self.fallback,
            "compensable": self.compensable,
            "gate_timeout_s": self.gate.timeout_s,
        }


@dataclass(frozen=True)
class Edge:
    from_stage: str
    to_stage: str
    kind: str = "hard"  # "hard" | "conditional" (target is conditional)


@dataclass(frozen=True)
class GraphDiff:
    added: frozenset[str]
    removed: frozenset[str]
    changed: frozenset[str]

    @property
    def is_empty(self) -> bool:
        return not (self.added or self.removed or self.changed)

    @property
    def touched(self) -> frozenset[str]:
        return self.added | self.removed | self.changed

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "added": sorted(self.added),
            "removed": sorted(self.removed),
            "changed": sorted(self.changed),
        }


class WorkflowGraph:
    def __init__(self, stages: dict[str, StageSpec], edges: tuple[Edge, ...]) -> None:
        self._stages = stages
        self._edges = edges
        self._order = self._toposort()

    # --- construction -------------------------------------------------------

    @classmethod
    def build(cls, specs: Iterable[StageSpec]) -> WorkflowGraph:
        stages: dict[str, StageSpec] = {}
        for spec in specs:
            if spec.name in stages:
                raise GraphError(f"duplicate stage {spec.name!r}")
            stages[spec.name] = spec
        edges: list[Edge] = []
        for spec in stages.values():
            for dep in spec.depends_on:
                if dep not in stages:
                    raise GraphError(f"stage {spec.name!r} depends on unknown stage {dep!r}")
                edges.append(Edge(dep, spec.name, "conditional" if spec.is_conditional else "hard"))
        return cls(stages, tuple(edges))

    def _toposort(self) -> list[str]:
        indeg = {name: len(spec.depends_on) for name, spec in self._stages.items()}
        order: list[str] = []
        ready = sorted(n for n, d in indeg.items() if d == 0)
        while ready:
            node = ready.pop(0)
            order.append(node)
            for dependant in sorted(self.dependants(node)):
                indeg[dependant] -= 1
                if indeg[dependant] == 0:
                    ready.append(dependant)
                    ready.sort()
        if len(order) != len(self._stages):
            raise GraphError("dependency cycle detected")
        return order

    # --- queries -------------------------------------------------------------

    @property
    def edges(self) -> tuple[Edge, ...]:
        return self._edges

    def names(self) -> list[str]:
        return list(self._order)

    def stage(self, name: str) -> StageSpec:
        return self._stages[name]

    def stages(self) -> list[StageSpec]:
        return [self._stages[n] for n in self._order]

    def topological_order(self) -> list[str]:
        return list(self._order)

    def dependants(self, name: str) -> set[str]:
        return {e.to_stage for e in self._edges if e.from_stage == name}

    def gates(self) -> list[str]:
        return [n for n in self._order if self._stages[n].is_gate]

    def evaluate_condition(self, name: str, ctx: Mapping[str, Any]) -> bool:
        spec = self._stages[name]
        return True if spec.condition is None else bool(spec.condition(ctx))

    def ready(self, states: Mapping[str, StageState]) -> list[str]:
        """Stages that may start now: PENDING with every dependency satisfied."""
        out: list[str] = []
        for name in self._order:
            if states.get(name, StageState.PENDING) is not StageState.PENDING:
                continue
            deps = self._stages[name].depends_on
            if all(states.get(d, StageState.PENDING).satisfies_dependency for d in deps):
                out.append(name)
        return out

    def downstream(self, names: Iterable[str]) -> set[str]:
        """Transitive dependants of ``names`` (excluding ``names`` themselves)."""
        seen: set[str] = set()
        frontier = list(names)
        while frontier:
            node = frontier.pop()
            for dep in self.dependants(node):
                if dep not in seen:
                    seen.add(dep)
                    frontier.append(dep)
        return seen

    def parallel_groups(self) -> dict[str, str]:
        """Stages that share the exact same dependency set form a parallel group."""
        by_deps: dict[tuple[str, ...], list[str]] = {}
        for name in self._order:
            deps = tuple(sorted(self._stages[name].depends_on))
            by_deps.setdefault(deps, []).append(name)
        groups: dict[str, str] = {}
        for deps, members in by_deps.items():
            if len(members) > 1 and deps:
                label = "after:" + "+".join(deps)
                for m in members:
                    groups[m] = label
        return groups

    def diff(self, other: WorkflowGraph) -> GraphDiff:
        mine, theirs = set(self._stages), set(other._stages)
        changed = {
            n for n in mine & theirs if self._stages[n].signature() != other._stages[n].signature()
        }
        return GraphDiff(
            added=frozenset(theirs - mine),
            removed=frozenset(mine - theirs),
            changed=frozenset(changed),
        )

    def to_dict(self) -> dict[str, Any]:
        groups = self.parallel_groups()
        return {
            "stages": [
                {
                    "name": s.name,
                    "agent": s.agent,
                    "owner": s.owner,
                    "depends_on": list(s.depends_on),
                    "condition": s.condition_label
                    or (s.condition.__name__ if s.condition else None),
                    "retry": s.signature()["retry"],
                    "timeout_s": s.timeout.seconds,
                    "fallback": s.fallback,
                    "compensable": s.compensable,
                    "gate_timeout_s": s.gate.timeout_s,
                    "gate_kind": s.gate_kind if s.is_gate else None,
                    "parallel_group": groups.get(s.name),
                    "purpose": s.purpose,
                    "emits": list(s.emits),
                }
                for s in self.stages()
            ],
            "edges": [
                {"from": e.from_stage, "to": e.to_stage, "kind": e.kind} for e in self._edges
            ],
        }
