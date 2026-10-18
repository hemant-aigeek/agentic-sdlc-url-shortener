"""WorkflowStore — the persistence port of the control plane (FR-O06, ADR-006).

Records are plain dataclasses so the engine never depends on SQLAlchemy. The
event log has an append method and read methods only: there is deliberately
no API to update or delete an event (NFR-05).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from agentic_sdlc.orchestration.context import RunContext
from agentic_sdlc.orchestration.events import AuditEvent
from agentic_sdlc.orchestration.states import RunState, StageState


@dataclass
class RunRecord:
    id: str
    title: str
    scope: str
    state: RunState
    requirement_raw: str
    requirement_version: int
    policy_version: str
    graph_version: int
    context: RunContext
    created_at: datetime
    updated_at: datetime
    terminal_reason: str | None = None


@dataclass
class StageRecord:
    run_id: str
    name: str
    owner: str
    state: StageState
    attempt: int = 0
    parallel_group: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    failure_kind: str | None = None
    fallback_used: bool = False
    last_error: str | None = None
    output: dict[str, Any] | None = None


@dataclass
class EdgeRecord:
    run_id: str
    graph_version: int
    from_stage: str
    to_stage: str
    kind: str


@dataclass
class ArtifactRecord:
    run_id: str
    stage: str
    kind: str
    version: int
    content: dict[str, Any]
    derived_from: list[int]
    policy_version: str
    created_at: datetime
    invalidated: bool = False
    id: int | None = None


@dataclass
class DecisionRecord:
    run_id: str
    gate: str
    actor: str
    decision: str  # approve | reject | clarify
    reason: str
    payload: dict[str, Any]
    artifact_version: int
    decided_at: datetime
    id: int | None = None


@dataclass
class ReplanRecord:
    run_id: str
    trigger: str
    graph_before: dict[str, Any]
    graph_after: dict[str, Any]
    invalidated: list[str]
    at: datetime
    id: int | None = None


@dataclass
class PolicyEvaluationRecord:
    run_id: str
    stage: str
    policy_id: str
    policy_version: str
    outcome: str
    detail: str
    at: datetime
    id: int | None = None


@dataclass
class PolicyExceptionRecord:
    run_id: str
    policy_id: str
    scope: str
    reason: str
    approver: str
    compensating_control: str
    approved_at: datetime
    expires_at: datetime | None
    status: str  # requested | approved | expired | rejected
    id: int | None = None


@dataclass
class MetricsSnapshot:
    run_id: str
    snapshot: dict[str, Any] = field(default_factory=dict)
    e2e_latency_s: float | None = None
    at: datetime | None = None


class WorkflowStore(ABC):
    # runs
    @abstractmethod
    def create_run(self, run: RunRecord) -> None: ...
    @abstractmethod
    def load_run(self, run_id: str) -> RunRecord | None: ...
    @abstractmethod
    def save_run(self, run: RunRecord) -> None: ...
    @abstractmethod
    def list_runs(self) -> list[RunRecord]: ...

    # stages & edges
    @abstractmethod
    def save_stage(self, stage: StageRecord) -> None: ...
    @abstractmethod
    def load_stages(self, run_id: str) -> dict[str, StageRecord]: ...
    @abstractmethod
    def delete_stages(self, run_id: str, names: list[str]) -> None: ...
    @abstractmethod
    def save_edges(self, edges: list[EdgeRecord]) -> None: ...
    @abstractmethod
    def load_edges(self, run_id: str, graph_version: int) -> list[EdgeRecord]: ...

    # events (append-only)
    @abstractmethod
    def append_event(self, event: AuditEvent) -> None: ...
    @abstractmethod
    def list_events(self, run_id: str) -> list[AuditEvent]: ...
    @abstractmethod
    def next_seq(self, run_id: str) -> int: ...

    # artifacts
    @abstractmethod
    def save_artifact(self, artifact: ArtifactRecord) -> int: ...
    @abstractmethod
    def list_artifacts(
        self, run_id: str, include_invalidated: bool = True
    ) -> list[ArtifactRecord]: ...
    @abstractmethod
    def invalidate_artifacts(self, run_id: str, stages: list[str]) -> list[int]: ...

    # decisions
    @abstractmethod
    def save_decision(self, decision: DecisionRecord) -> int: ...
    @abstractmethod
    def list_decisions(self, run_id: str) -> list[DecisionRecord]: ...

    # replanning, policy, metrics
    @abstractmethod
    def save_replan(self, replan: ReplanRecord) -> int: ...
    @abstractmethod
    def list_replans(self, run_id: str) -> list[ReplanRecord]: ...
    @abstractmethod
    def save_policy_evaluation(self, evaluation: PolicyEvaluationRecord) -> int: ...
    @abstractmethod
    def list_policy_evaluations(self, run_id: str) -> list[PolicyEvaluationRecord]: ...
    @abstractmethod
    def save_policy_exception(self, exc: PolicyExceptionRecord) -> int: ...
    @abstractmethod
    def list_policy_exceptions(self, run_id: str) -> list[PolicyExceptionRecord]: ...
    @abstractmethod
    def save_metrics(self, metrics: MetricsSnapshot) -> None: ...
    @abstractmethod
    def load_metrics(self, run_id: str) -> MetricsSnapshot | None: ...
