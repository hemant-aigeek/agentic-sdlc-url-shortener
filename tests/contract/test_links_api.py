"""FR-U01..U13 over HTTP: the v1 link API contract, auth (AMB-06), rate limit (AMB-07)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from agentic_sdlc.api.app import create_app
from agentic_sdlc.config import Settings

pytestmark = pytest.mark.contract

KEY = {"X-API-Key": "test-key"}


def make_client(**overrides: object) -> TestClient:
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        api_key="test-key",
        base_url="http://short.test",
        rate_limit_capacity=1000,
        **overrides,  # type: ignore[arg-type]
    )
    return TestClient(create_app(settings), raise_server_exceptions=False)


@pytest.fixture
def client() -> TestClient:
    return make_client()


def create(client: TestClient, **body: object) -> dict[str, object]:
    r = client.post(
        "/api/v1/links", json={"target_url": "https://example.com/a", **body}, headers=KEY
    )
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


@pytest.mark.req("FR-U01")
def test_create_returns_201_with_contract_fields(client: TestClient) -> None:
    body = create(client)
    assert set(body) >= {"code", "short_url", "target_url", "created_at", "expires_at"}
    assert len(body["code"]) == 7  # type: ignore[arg-type]
    assert body["short_url"] == f"http://short.test/{body['code']}"
    assert body["expires_at"] is None


@pytest.mark.req("FR-U02", "FR-U13")
@pytest.mark.parametrize("url", ["javascript:alert(1)", "ftp://x.example/", "http://127.0.0.1/"])
def test_create_rejects_invalid_url_with_field_error(client: TestClient, url: str) -> None:
    r = client.post("/api/v1/links", json={"target_url": url}, headers=KEY)
    assert r.status_code == 422
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert body["errors"][0]["field"] == "target_url"
    assert "traceback" not in r.text.lower()


@pytest.mark.req("FR-U13")
def test_create_with_missing_body_field_is_problem_422(client: TestClient) -> None:
    r = client.post("/api/v1/links", json={}, headers=KEY)
    assert r.status_code == 422
    assert r.json()["errors"][0]["field"] == "target_url"


@pytest.mark.req("FR-U05")
def test_redirect_is_temporary_and_points_at_target(client: TestClient) -> None:
    code = create(client)["code"]
    r = client.get(f"/{code}", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "https://example.com/a"
    assert "no-store" in r.headers.get("cache-control", "")


@pytest.mark.req("FR-U05")
def test_redirect_unknown_code_is_404_problem(client: TestClient) -> None:
    r = client.get("/zzzzzzz", follow_redirects=False)
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/problem+json")


@pytest.mark.req("FR-U05")
def test_redirect_malformed_code_is_404_not_500(client: TestClient) -> None:
    r = client.get("/not-a-valid-code-!!", follow_redirects=False)
    assert r.status_code == 404


@pytest.mark.req("FR-U06")
def test_expired_link_is_410_gone(client: TestClient) -> None:
    code = create(client, expires_at=(datetime.now(UTC) + timedelta(milliseconds=200)).isoformat())[
        "code"
    ]
    import time

    time.sleep(0.3)
    r = client.get(f"/{code}", follow_redirects=False)
    assert r.status_code == 410


@pytest.mark.req("FR-U06")
def test_past_expiry_rejected_at_creation(client: TestClient) -> None:
    r = client.post(
        "/api/v1/links",
        json={"target_url": "https://example.com", "expires_at": "2000-01-01T00:00:00Z"},
        headers=KEY,
    )
    assert r.status_code == 422
    assert r.json()["errors"][0]["field"] == "expires_at"


@pytest.mark.req("FR-U07", "FR-U08")
def test_analytics_reflects_redirects(client: TestClient) -> None:
    code = create(client)["code"]
    for _ in range(3):
        client.get(
            f"/{code}", follow_redirects=False, headers={"user-agent": "Mozilla/5.0 Chrome/1"}
        )
    r = client.get(f"/api/v1/links/{code}/analytics", headers=KEY)
    assert r.status_code == 200
    body = r.json()
    assert body["total_redirects"] == 3
    assert sum(body["redirects_by_day"].values()) == 3
    assert body["first_redirect_at"] <= body["last_redirect_at"]


@pytest.mark.req("FR-U08")
def test_analytics_unknown_code_404(client: TestClient) -> None:
    assert client.get("/api/v1/links/zzzzzzz/analytics", headers=KEY).status_code == 404


@pytest.mark.req("FR-U01")
def test_get_link_metadata(client: TestClient) -> None:
    code = create(client)["code"]
    r = client.get(f"/api/v1/links/{code}", headers=KEY)
    assert r.status_code == 200 and r.json()["code"] == code


@pytest.mark.req("FR-U09")
def test_idempotent_create(client: TestClient) -> None:
    first = client.post(
        "/api/v1/links",
        json={"target_url": "https://example.com/i"},
        headers={**KEY, "Idempotency-Key": "abc"},
    )
    second = client.post(
        "/api/v1/links",
        json={"target_url": "https://example.com/i"},
        headers={**KEY, "Idempotency-Key": "abc"},
    )
    assert first.status_code == 201 and second.status_code == 200
    assert first.json()["code"] == second.json()["code"]
    conflict = client.post(
        "/api/v1/links",
        json={"target_url": "https://example.com/other"},
        headers={**KEY, "Idempotency-Key": "abc"},
    )
    assert conflict.status_code == 409


@pytest.mark.req("NFR-01")
@pytest.mark.security
def test_mutating_endpoints_require_api_key(client: TestClient) -> None:
    assert (
        client.post("/api/v1/links", json={"target_url": "https://example.com"}).status_code == 401
    )
    assert (
        client.post(
            "/api/v1/links",
            json={"target_url": "https://example.com"},
            headers={"X-API-Key": "wrong"},
        ).status_code
        == 401
    )
    code = create(client)["code"]
    # the public redirect path needs no key
    assert client.get(f"/{code}", follow_redirects=False).status_code == 307
    # analytics is read-only but not public
    assert client.get(f"/api/v1/links/{code}/analytics").status_code == 401


@pytest.mark.req("NFR-01")
def test_rate_limit_on_creation() -> None:
    limited = make_client(rate_limit_capacity=3, rate_limit_refill_per_second=0.0)
    statuses = [
        limited.post(
            "/api/v1/links", json={"target_url": "https://example.com"}, headers=KEY
        ).status_code
        for _ in range(5)
    ]
    assert statuses == [201, 201, 201, 429, 429]
    r = limited.post("/api/v1/links", json={"target_url": "https://example.com"}, headers=KEY)
    assert "retry-after" in {k.lower() for k in r.headers}


@pytest.mark.req("FR-U11")
def test_persistence_failure_is_503_problem_not_500() -> None:
    client = make_client()
    from agentic_sdlc.persistence.db import Database

    client.app.state.db = Database("sqlite+pysqlite:////nonexistent-dir/x.db")  # type: ignore[attr-defined]
    r = client.post("/api/v1/links", json={"target_url": "https://example.com"}, headers=KEY)
    assert r.status_code == 503
    assert r.headers["content-type"].startswith("application/problem+json")


@pytest.mark.req("NFR-04")
def test_correlation_id_is_echoed_and_generated(client: TestClient) -> None:
    r = client.get("/health/live", headers={"X-Correlation-ID": "abc-123"})
    assert r.headers["x-correlation-id"] == "abc-123"
    r2 = client.get("/health/live")
    assert len(r2.headers["x-correlation-id"]) >= 8
