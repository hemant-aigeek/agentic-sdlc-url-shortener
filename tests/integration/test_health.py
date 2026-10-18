"""FR-U12: liveness and readiness endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agentic_sdlc.api.app import create_app
from agentic_sdlc.config import Settings


@pytest.fixture
def client() -> TestClient:
    app = create_app(Settings(database_url="sqlite+pysqlite:///:memory:", api_key="test-key"))
    return TestClient(app)


@pytest.mark.integration
@pytest.mark.req("FR-U12")
def test_live_returns_ok(client: TestClient) -> None:
    r = client.get("/health/live")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.integration
@pytest.mark.req("FR-U12")
def test_ready_checks_database(client: TestClient) -> None:
    r = client.get("/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"] == "ok"


@pytest.mark.integration
@pytest.mark.req("FR-U12", "FR-U13")
def test_ready_fails_when_database_unavailable() -> None:
    app = create_app(Settings(database_url="sqlite+pysqlite:///:memory:", api_key="test-key"))
    # simulate dependency failure by disposing the engine and pointing it at an unopenable path
    from agentic_sdlc.persistence.db import Database

    app.state.db = Database("sqlite+pysqlite:////nonexistent-dir/x.db")
    r = TestClient(app, raise_server_exceptions=False).get("/health/ready")
    assert r.status_code == 503
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["checks"]["database"] == "fail"


@pytest.mark.integration
@pytest.mark.req("FR-U13")
def test_unknown_route_is_problem_json(client: TestClient) -> None:
    r = client.get("/api/v1/does-not-exist")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert {"type", "title", "status", "detail", "instance"} <= body.keys()
    assert "stack" not in body and "traceback" not in body.get("detail", "")
