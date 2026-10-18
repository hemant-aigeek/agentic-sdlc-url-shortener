"""FR-O06, FR-O07, NFR-04, NFR-05 / ADR-006: workflow persistence and event-log reconstruction."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest

from agentic_sdlc.orchestration.context import ArtifactRef, RunContext
from agentic_sdlc.orchestration.events import ActorType, AuditEvent, EventKind
from agentic_sdlc.orchestration.states import RunState, StageState
from agentic_sdlc.orchestration.store import (
    ArtifactRecord,
    DecisionRecord,
    EdgeRecord,
    RunRecord,
    StageRecord,
    WorkflowStore,
)
from agentic_sdlc.persistence.db import Database
from agentic_sdlc.persistence.workflow_store import SqlWorkflowStore

pytestmark = pytest.mark.orchestration

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


@pytest.fixture
def store() -> Iterator[WorkflowStore]:
    db = Database("sqlite+pysqlite:///:memory:")
    db.create_all()
    yield SqlWorkflowStore(db)
    db.dispose()


def make_run(run_id: str = "run-1") -> RunRecord:
    ctx = RunContext(run_id=run_id, title="t", scope="greenfield", requirement_raw="req")
    return RunRecord(
        id=run_id,
        title="t",
        scope="greenfield",
        state=RunState.CREATED,
        requirement_raw="req",
        requirement_version=1,
        policy_version="1.0.0",
        graph_version=1,
        context=ctx,
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.mark.req("FR-O06")
def test_run_roundtrip_including_context(store: WorkflowStore) -> None:
    run = make_run()
    run.context.data["normalized"] = {"intent": "x"}
    run.context.outputs["ingest"] = {"ok": True}
    run.context.artifacts["design"] = ArtifactRef(id=7, kind="design", version=2, stage="design")
    store.create_run(run)
    run.state = RunState.RUNNING
    store.save_run(run)
    loaded = store.load_run("run-1")
    assert loaded is not None
    assert loaded.state is RunState.RUNNING
    assert loaded.context.data["normalized"] == {"intent": "x"}
    assert loaded.context.outputs["ingest"] == {"ok": True}
    assert loaded.context.artifacts["design"].version == 2
    assert loaded.created_at == NOW


@pytest.mark.req("FR-O06")
def test_stage_upsert_and_load(store: WorkflowStore) -> None:
    store.create_run(make_run())
    stage = StageRecord(run_id="run-1", name="a", owner="agent", state=StageState.PENDING)
    store.save_stage(stage)
    stage.state = StageState.RUNNING
    stage.attempt = 2
    stage.started_at = NOW
    store.save_stage(stage)
    loaded = store.load_stages("run-1")["a"]
    assert loaded.state is StageState.RUNNING and loaded.attempt == 2 and loaded.started_at == NOW


@pytest.mark.req("FR-O02", "FR-O06")
def test_edges_are_versioned_per_graph(store: WorkflowStore) -> None:
    store.create_run(make_run())
    store.save_edges(
        [EdgeRecord("run-1", 1, "a", "b", "hard"), EdgeRecord("run-1", 2, "a", "c", "hard")]
    )
    assert [e.to_stage for e in store.load_edges("run-1", 1)] == ["b"]
    assert [e.to_stage for e in store.load_edges("run-1", 2)] == ["c"]


@pytest.mark.req("NFR-05")
def test_event_log_is_append_only_and_sequenced(store: WorkflowStore) -> None:
    store.create_run(make_run())
    for i in range(3):
        store.append_event(
            AuditEvent(
                "run-1",
                store.next_seq("run-1"),
                EventKind.STAGE_STARTED,
                ActorType.AGENT,
                NOW + timedelta(seconds=i),
                stage=f"s{i}",
            )
        )
    events = store.list_events("run-1")
    assert [e.seq for e in events] == [1, 2, 3]
    assert not any(name.startswith(("update_event", "delete_event")) for name in dir(store))


@pytest.mark.req("NFR-05")
def test_duplicate_sequence_is_rejected(store: WorkflowStore) -> None:
    from sqlalchemy.exc import IntegrityError

    from agentic_sdlc.errors import StoreUnavailableError

    store.create_run(make_run())
    store.append_event(AuditEvent("run-1", 1, EventKind.RUN_CREATED, ActorType.SYSTEM, NOW))
    with pytest.raises((IntegrityError, StoreUnavailableError)):
        store.append_event(AuditEvent("run-1", 1, EventKind.RUN_CREATED, ActorType.SYSTEM, NOW))


@pytest.mark.req("FR-O07")
def test_artifacts_carry_lineage_and_policy_version(store: WorkflowStore) -> None:
    store.create_run(make_run())
    a = ArtifactRecord("run-1", "ingest", "normalized_requirement", 1, {"x": 1}, [], "1.0.0", NOW)
    a_id = store.save_artifact(a)
    b = ArtifactRecord("run-1", "design", "design", 1, {"y": 2}, [a_id], "1.0.0", NOW)
    b_id = store.save_artifact(b)
    arts = {x.kind: x for x in store.list_artifacts("run-1")}
    assert arts["design"].derived_from == [a_id]
    assert arts["design"].policy_version == "1.0.0"
    assert b_id > a_id


@pytest.mark.req("FR-O14")
def test_invalidate_artifacts_by_stage(store: WorkflowStore) -> None:
    store.create_run(make_run())
    store.save_artifact(ArtifactRecord("run-1", "design", "design", 1, {}, [], "1.0.0", NOW))
    store.save_artifact(ArtifactRecord("run-1", "ingest", "req", 1, {}, [], "1.0.0", NOW))
    ids = store.invalidate_artifacts("run-1", ["design"])
    assert len(ids) == 1
    live = store.list_artifacts("run-1", include_invalidated=False)
    assert [a.kind for a in live] == ["req"]


@pytest.mark.req("FR-G03")
def test_decisions_are_attributable(store: WorkflowStore) -> None:
    store.create_run(make_run())
    store.save_decision(
        DecisionRecord(
            "run-1", "design_approval", "hemant", "approve", "looks right", {"ack": True}, 1, NOW
        )
    )
    d = store.list_decisions("run-1")[0]
    assert (d.actor, d.decision, d.reason, d.payload, d.decided_at) == (
        "hemant",
        "approve",
        "looks right",
        {"ack": True},
        NOW,
    )


@pytest.mark.req("NFR-04")
def test_stage_states_can_be_reconstructed_from_events_alone(store: WorkflowStore) -> None:
    """The event log, not the stage table, is the source of truth for reconstruction."""
    store.create_run(make_run())
    seq = 0

    def emit(kind: EventKind, stage: str, result: str | None = None) -> None:
        nonlocal seq
        seq += 1
        store.append_event(
            AuditEvent(
                "run-1",
                seq,
                kind,
                ActorType.AGENT,
                NOW + timedelta(seconds=seq),
                stage=stage,
                result=result,
            )
        )

    emit(EventKind.STAGE_STARTED, "a")
    emit(EventKind.STAGE_SUCCEEDED, "a", "SUCCEEDED")
    emit(EventKind.STAGE_STARTED, "b")
    emit(EventKind.STAGE_FAILED, "b", "FAILED")
    emit(EventKind.RETRY_SCHEDULED, "b")
    emit(EventKind.STAGE_STARTED, "b")
    emit(EventKind.STAGE_SUCCEEDED, "b", "SUCCEEDED")
    emit(EventKind.STAGE_STARTED, "c")

    from agentic_sdlc.orchestration.reconstruct import reconstruct_stage_states

    states, attempts = reconstruct_stage_states(store.list_events("run-1"))
    assert states == {"a": StageState.SUCCEEDED, "b": StageState.SUCCEEDED, "c": StageState.RUNNING}
    assert attempts == {"a": 1, "b": 2, "c": 1}
