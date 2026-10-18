"""Control-plane schemas (plan §2): workflow runs, graph view, events, decisions."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

WORKFLOW_SCHEMA_VERSION = "1.0.0"


class _Versioned(BaseModel):
    model_config = ConfigDict(json_schema_extra={"x-schema-version": WORKFLOW_SCHEMA_VERSION})


class WorkflowCreateRequest(_Versioned):
    title: str = Field(..., max_length=200)
    requirement: str = Field(..., max_length=20_000)
    scope: Literal["greenfield", "brownfield", "ambiguous", "auto"] = "auto"
    planner: str = "sdlc"
    data: dict[str, Any] = Field(default_factory=dict)
    run: bool = Field(
        default=True, description="Advance immediately until a gate or terminal state"
    )


class StageView(_Versioned):
    name: str
    agent: str
    owner: str
    depends_on: list[str]
    condition: str | None
    state: str | None = None
    attempt: int | None = None
    parallel_group: str | None
    started_at: str | None = None
    ended_at: str | None = None
    failure_kind: str | None = None
    fallback_used: bool | None = None
    fallback: str | None
    gate_kind: str | None = None
    purpose: str = ""


class EdgeView(_Versioned):
    from_: str = Field(alias="from")
    to: str
    kind: str
    model_config = ConfigDict(
        populate_by_name=True, json_schema_extra={"x-schema-version": WORKFLOW_SCHEMA_VERSION}
    )


class GraphView(_Versioned):
    run_state: str
    graph_version: int
    open_gates: list[str]
    stages: list[StageView]
    edges: list[EdgeView]


class WorkflowRunView(_Versioned):
    id: str
    title: str
    scope: str
    state: str
    requirement_version: int
    graph_version: int
    policy_version: str
    created_at: datetime
    updated_at: datetime
    terminal_reason: str | None
    open_gates: list[str]
    stage_states: dict[str, str]


class AuditEventView(_Versioned):
    seq: int
    kind: str
    actor_type: str
    at: datetime
    stage: str | None
    attempt: int | None
    target: str | None
    result: str | None
    reason: str | None
    data: dict[str, Any]


class DecisionRequest(_Versioned):
    decision: Literal["approve", "reject", "clarify"]
    reason: str = Field(..., min_length=1, max_length=2000)
    payload: dict[str, Any] = Field(default_factory=dict)
    run: bool = Field(default=True, description="Advance after recording the decision")


class DecisionView(_Versioned):
    id: int | None
    gate: str
    actor: str
    decision: str
    reason: str
    payload: dict[str, Any]
    artifact_version: int
    decided_at: datetime


class GateView(_Versioned):
    gate: str
    kind: str
    opened_at: str | None
    timeout_s: float | None
    purpose: str
    options: list[str]
    context: dict[str, Any]


class ArtifactView(_Versioned):
    id: int | None
    stage: str
    kind: str
    version: int
    derived_from: list[int]
    policy_version: str
    invalidated: bool
    created_at: datetime
    content: dict[str, Any]


class StopRequest(_Versioned):
    reason: str = Field(..., min_length=1, max_length=2000)


EXPORTED = [
    WorkflowCreateRequest,
    WorkflowRunView,
    GraphView,
    AuditEventView,
    DecisionRequest,
    DecisionView,
    GateView,
    ArtifactView,
]
