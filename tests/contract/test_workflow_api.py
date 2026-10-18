"""FR-O01, FR-O02, FR-O20, FR-G02, FR-G03 over HTTP: workflow inspection and human decisions."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from tests.orchestration.conftest import ScriptedAgent, stage

from agentic_sdlc.api.app import create_app
from agentic_sdlc.config import Settings
from agentic_sdlc.orchestration.agents.base import AgentRegistry
from agentic_sdlc.orchestration.context import RunContext
from agentic_sdlc.orchestration.graph import WorkflowGraph

pytestmark = pytest.mark.contract

KEY = {"X-API-Key": "test-key"}
ACTOR = {**KEY, "X-Actor": "hemant"}


def gated(_: RunContext) -> WorkflowGraph:
    return WorkflowGraph.build(
        [
            stage("a"),
            stage("approve", "a", owner="human", purpose="design approval"),
            stage("b", "approve"),
        ]
    )


@pytest.fixture
def client(tmp_path: Any) -> Iterator[TestClient]:
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        api_key="test-key",
        data_dir=tmp_path,
        log_json=False,
    )
    app = create_app(settings)
    # swap in a scripted planner + agent so the API tests do not depend on the SDLC agents
    app.state.engine = app.state.engine_factory(
        agents=AgentRegistry({"scripted": ScriptedAgent()}), planners={"gated": gated}
    )
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def create(client: TestClient, **body: Any) -> dict[str, Any]:
    payload = {
        "title": "t",
        "requirement": "do x",
        "scope": "greenfield",
        "planner": "gated",
        **body,
    }
    r = client.post("/api/v1/workflows", json=payload, headers=KEY)
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


@pytest.mark.req("FR-O01")
def test_create_runs_to_first_gate(client: TestClient) -> None:
    body = create(client)
    assert body["state"] == "WAITING_APPROVAL" and body["open_gates"] == ["approve"]
    assert body["stage_states"] == {"a": "SUCCEEDED", "approve": "READY", "b": "PENDING"}
    assert body["policy_version"]


@pytest.mark.req("FR-O02")
def test_graph_and_events_are_inspectable(client: TestClient) -> None:
    run_id = create(client)["id"]
    g = client.get(f"/api/v1/workflows/{run_id}/graph", headers=KEY).json()
    assert [s["name"] for s in g["stages"]] == ["a", "approve", "b"]
    assert g["edges"] == [
        {"from": "a", "to": "approve", "kind": "hard"},
        {"from": "approve", "to": "b", "kind": "hard"},
    ]
    events = client.get(f"/api/v1/workflows/{run_id}/events", headers=KEY).json()
    assert events[0]["kind"] == "run_created" and events[-1]["kind"] == "gate_opened"
    assert all({"seq", "actor_type", "at", "result", "reason"} <= set(e) for e in events)


@pytest.mark.req("FR-G02")
def test_gate_listing_exposes_context_and_options(client: TestClient) -> None:
    run_id = create(client)["id"]
    gates = client.get(f"/api/v1/workflows/{run_id}/gates", headers=KEY).json()
    assert gates[0]["gate"] == "approve" and gates[0]["options"] == ["approve", "reject"]
    assert "a" in gates[0]["context"]["upstream_outputs"]


@pytest.mark.req("FR-G03")
def test_decision_requires_actor_and_is_recorded(client: TestClient) -> None:
    run_id = create(client)["id"]
    no_actor = client.post(
        f"/api/v1/workflows/{run_id}/gates/approve/decision",
        json={"decision": "approve", "reason": "ok"},
        headers=KEY,
    )
    assert no_actor.status_code == 401
    r = client.post(
        f"/api/v1/workflows/{run_id}/gates/approve/decision",
        json={"decision": "approve", "reason": "ok"},
        headers=ACTOR,
    )
    assert r.status_code == 201
    assert r.json()["actor"] == "hemant" and r.json()["decision"] == "approve"
    run = client.get(f"/api/v1/workflows/{run_id}", headers=KEY).json()
    assert run["state"] == "COMPLETED"
    decisions = client.get(f"/api/v1/workflows/{run_id}/decisions", headers=KEY).json()
    assert len(decisions) == 1 and decisions[0]["gate"] == "approve"


@pytest.mark.req("FR-G01")
def test_decision_on_closed_gate_is_409_problem(client: TestClient) -> None:
    run_id = create(client)["id"]
    r = client.post(
        f"/api/v1/workflows/{run_id}/gates/b/decision",
        json={"decision": "approve", "reason": "x"},
        headers=ACTOR,
    )
    assert r.status_code == 409 and r.headers["content-type"].startswith("application/problem+json")


@pytest.mark.req("FR-O13")
def test_resume_and_stop(client: TestClient) -> None:
    run_id = create(client)["id"]
    assert (
        client.post(f"/api/v1/workflows/{run_id}/resume", headers=KEY).json()["state"]
        == "WAITING_APPROVAL"
    )
    r = client.post(f"/api/v1/workflows/{run_id}/stop", json={"reason": "halt"}, headers=ACTOR)
    assert r.json()["state"] == "SAFE_STOPPED" and r.json()["terminal_reason"].startswith(
        "OPERATOR_STOP"
    )


@pytest.mark.req("FR-O07")
def test_artifacts_and_lineage(client: TestClient) -> None:
    run_id = create(client)["id"]
    arts = client.get(f"/api/v1/workflows/{run_id}/artifacts", headers=KEY).json()
    assert [a["kind"] for a in arts] == ["a_artifact"]
    lineage = client.get(f"/api/v1/workflows/{run_id}/lineage", headers=KEY).json()
    assert lineage["artifacts"][0]["derived_from"] == []


@pytest.mark.req("FR-O01")
def test_unknown_workflow_is_404_problem(client: TestClient) -> None:
    r = client.get("/api/v1/workflows/nope", headers=KEY)
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/problem+json")
