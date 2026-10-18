"""Security controls (NFR-01, constitution V, SEC-002): what must never leak or be accepted."""

from __future__ import annotations

import io
import json
from collections.abc import Iterator
from typing import Any

import pytest
import structlog
from fastapi.testclient import TestClient

from agentic_sdlc.api.app import create_app
from agentic_sdlc.config import Settings
from agentic_sdlc.telemetry.logging import _redact, get_logger

pytestmark = pytest.mark.security

KEY = "test-key-0123456789"
HEADERS = {"X-API-Key": KEY}


@pytest.fixture
def client(tmp_path: Any) -> Iterator[TestClient]:
    app = create_app(
        Settings(
            database_url="sqlite+pysqlite:///:memory:",
            api_key=KEY,
            data_dir=tmp_path,
            log_json=True,
        )
    )
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.mark.req("FR-U03", "NFR-01")
@pytest.mark.parametrize(
    "target",
    [
        "http://127.0.0.1/admin",
        "http://localhost:8000/",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/internal",
        "http://192.168.1.1/",
        "http://[::1]/",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://service.local/",
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "file:///etc/passwd",
        "ftp://example.com/x",
        "//example.com/protocol-relative",
    ],
)
def test_redirector_abuse_targets_are_rejected(client: TestClient, target: str) -> None:
    r = client.post("/api/v1/links", json={"target_url": target}, headers=HEADERS)
    assert r.status_code == 422, r.text
    body = r.json()
    assert body["title"] and "target_url" in json.dumps(body["errors"])


@pytest.mark.req("FR-U13", "NFR-01")
def test_problem_responses_never_contain_tracebacks_or_internals(client: TestClient) -> None:
    for r in (
        client.get("/r/does-not-exist"),
        client.post("/api/v1/links", json={"target_url": "nope"}, headers=HEADERS),
        client.get("/api/v1/workflows/missing", headers=HEADERS),
        client.post("/api/v1/links", json={"target_url": "https://x.io"}),  # no key
    ):
        text = r.text
        assert r.status_code in {401, 404, 422}
        for needle in ("Traceback", 'File "', "sqlalchemy", "agentic_sdlc/", KEY):
            assert needle not in text, f"{needle!r} leaked in {r.status_code} response"
        assert r.headers["content-type"].startswith("application/problem+json")


@pytest.mark.req("FR-G03", "NFR-11")
def test_decisions_require_an_attributable_actor(client: TestClient) -> None:
    r = client.post(
        "/api/v1/workflows/any/gates/design_approval/decision",
        json={"decision": "approve", "reason": "x"},
        headers=HEADERS,  # key but no actor
    )
    assert r.status_code == 401
    assert "X-Actor" in r.json()["detail"]
    r = client.post(
        "/api/v1/workflows/any/gates/design_approval/decision",
        json={"decision": "approve", "reason": "x"},
        headers={"X-Actor": "someone"},  # actor but no key
    )
    assert r.status_code == 401


@pytest.mark.req("NFR-01")
def test_api_key_is_redacted_from_structured_logs() -> None:
    event = _redact(None, "info", {"event": "x", "api_key": KEY, "X-API-Key": KEY, "run_id": "r"})
    assert event["api_key"] == "***" and event["X-API-Key"] == "***" and event["run_id"] == "r"


@pytest.mark.req("NFR-01", "NFR-04")
def test_log_lines_carry_bound_context_and_no_secret(capsys: pytest.CaptureFixture[str]) -> None:
    stream = io.StringIO()
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _redact,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(stream),
        cache_logger_on_first_use=False,
    )
    structlog.contextvars.bind_contextvars(run_id="run-1")
    try:
        get_logger("t").info("something", authorization=f"Bearer {KEY}")
    finally:
        structlog.contextvars.unbind_contextvars("run_id")
    line = json.loads(stream.getvalue().strip())
    assert line["run_id"] == "run-1"
    assert line["authorization"] == "***" and KEY not in stream.getvalue()


@pytest.mark.req("FR-U02", "NFR-01")
def test_target_url_length_is_bounded(client: TestClient) -> None:
    r = client.post(
        "/api/v1/links", json={"target_url": "https://example.com/" + "a" * 5000}, headers=HEADERS
    )
    assert r.status_code == 422
