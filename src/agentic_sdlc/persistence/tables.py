"""SQLAlchemy Core table definitions for both planes (see specs/.../data-model.md).

No foreign keys cross the plane boundary (ADR-001). Control-plane tables are
defined here from the start so that ``create_all`` is a single step.
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
)

SCHEMA_VERSION = 1

metadata = MetaData()

schema_version = Table(
    "schema_version",
    metadata,
    Column("version", Integer, primary_key=True),
)

# --- application plane ------------------------------------------------------

short_links = Table(
    "short_links",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("code", String(16), nullable=False, unique=True),
    Column("target_url", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=True),
    Column("idempotency_key", String(128), nullable=True, unique=True),
    Column("payload_hash", String(64), nullable=True),
)

redirect_events = Table(
    "redirect_events",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("code", String(16), nullable=False),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Column("referrer", Text, nullable=True),
    Column("ua_class", String(16), nullable=True),
    Index("ix_redirect_events_code_time", "code", "occurred_at"),
)

# --- control plane ----------------------------------------------------------

workflow_runs = Table(
    "workflow_runs",
    metadata,
    Column("id", String(32), primary_key=True),
    Column("title", Text, nullable=False),
    Column("scope", String(16), nullable=False),
    Column("state", String(32), nullable=False),
    Column("requirement_raw", Text, nullable=False),
    Column("requirement_version", Integer, nullable=False, default=1),
    Column("policy_version", String(16), nullable=False),
    Column("graph_version", Integer, nullable=False, default=1),
    Column("context", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("terminal_reason", Text, nullable=True),
)

workflow_stages = Table(
    "workflow_stages",
    metadata,
    Column("run_id", String(32), ForeignKey("workflow_runs.id"), primary_key=True),
    Column("name", String(64), primary_key=True),
    Column("owner", String(8), nullable=False),
    Column("state", String(16), nullable=False),
    Column("attempt", Integer, nullable=False, default=0),
    Column("parallel_group", String(64), nullable=True),
    Column("started_at", DateTime(timezone=True), nullable=True),
    Column("ended_at", DateTime(timezone=True), nullable=True),
    Column("failure_kind", String(16), nullable=True),
    Column("fallback_used", Boolean, nullable=False, default=False),
    Column("last_error", Text, nullable=True),
    Column("output", JSON, nullable=True),
)

workflow_edges = Table(
    "workflow_edges",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("run_id", String(32), ForeignKey("workflow_runs.id"), nullable=False),
    Column("graph_version", Integer, nullable=False),
    Column("from_stage", String(64), nullable=False),
    Column("to_stage", String(64), nullable=False),
    Column("kind", String(16), nullable=False),
)

workflow_artifacts = Table(
    "workflow_artifacts",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("run_id", String(32), ForeignKey("workflow_runs.id"), nullable=False),
    Column("stage", String(64), nullable=False),
    Column("kind", String(64), nullable=False),
    Column("version", Integer, nullable=False, default=1),
    Column("content", JSON, nullable=False),
    Column("derived_from", JSON, nullable=False),
    Column("policy_version", String(16), nullable=False),
    Column("invalidated", Boolean, nullable=False, default=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Index("ix_artifacts_run_kind", "run_id", "kind"),
)

workflow_decisions = Table(
    "workflow_decisions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("run_id", String(32), ForeignKey("workflow_runs.id"), nullable=False),
    Column("gate", String(64), nullable=False),
    Column("actor", String(128), nullable=False),
    Column("decision", String(16), nullable=False),
    Column("reason", Text, nullable=False),
    Column("payload", JSON, nullable=False),
    Column("artifact_version", Integer, nullable=False),
    Column("decided_at", DateTime(timezone=True), nullable=False),
)

workflow_events = Table(
    "workflow_events",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("run_id", String(32), ForeignKey("workflow_runs.id"), nullable=False),
    Column("seq", Integer, nullable=False),
    Column("kind", String(32), nullable=False),
    Column("actor_type", String(8), nullable=False),
    Column("stage", String(64), nullable=True),
    Column("attempt", Integer, nullable=True),
    Column("target", String(128), nullable=True),
    Column("result", String(32), nullable=True),
    Column("reason", Text, nullable=True),
    Column("data", JSON, nullable=False),
    Column("at", DateTime(timezone=True), nullable=False),
    Index("ix_events_run_seq", "run_id", "seq", unique=True),
)

replan_events = Table(
    "replan_events",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("run_id", String(32), ForeignKey("workflow_runs.id"), nullable=False),
    Column("trigger", Text, nullable=False),
    Column("graph_before", JSON, nullable=False),
    Column("graph_after", JSON, nullable=False),
    Column("invalidated", JSON, nullable=False),
    Column("at", DateTime(timezone=True), nullable=False),
)

policy_evaluations = Table(
    "policy_evaluations",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("run_id", String(32), ForeignKey("workflow_runs.id"), nullable=False),
    Column("stage", String(64), nullable=False),
    Column("policy_id", String(16), nullable=False),
    Column("policy_version", String(16), nullable=False),
    Column("outcome", String(24), nullable=False),
    Column("detail", Text, nullable=False),
    Column("at", DateTime(timezone=True), nullable=False),
)

policy_exceptions = Table(
    "policy_exceptions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("run_id", String(32), ForeignKey("workflow_runs.id"), nullable=False),
    Column("policy_id", String(16), nullable=False),
    Column("scope", Text, nullable=False),
    Column("reason", Text, nullable=False),
    Column("approver", String(128), nullable=False),
    Column("compensating_control", Text, nullable=False),
    Column("approved_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=True),
    Column("status", String(16), nullable=False),
)

run_metrics = Table(
    "run_metrics",
    metadata,
    Column("run_id", String(32), ForeignKey("workflow_runs.id"), primary_key=True),
    Column("snapshot", JSON, nullable=False),
    Column("e2e_latency_s", Float, nullable=True),
    Column("at", DateTime(timezone=True), nullable=False),
)
