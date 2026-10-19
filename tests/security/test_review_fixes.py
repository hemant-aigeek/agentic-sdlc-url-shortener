"""Regression tests for the pre-submission review findings (FR-G09, FR-U02, FR-U03, NFR-01)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from agentic_sdlc.api.app import create_app
from agentic_sdlc.config import Settings
from agentic_sdlc.domain.validation import UrlPolicy, validate_target_url
from agentic_sdlc.errors import ValidationError
from agentic_sdlc.orchestration.agents.delivery import _inside

pytestmark = pytest.mark.security

KEY = "test-key-0123456789"
H = {"X-API-Key": KEY, "X-Actor": "alice"}
REQ = (
    "Users can create a short link for a URL and get redirected when they visit it. "
    "Links expire after 30 days."
)
REPO = Path(__file__).resolve().parents[2]


def _client(tmp_path: Path, **overrides: Any) -> TestClient:
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        api_key=KEY,
        data_dir=tmp_path,
        log_json=True,
        repository_root=REPO,
        verify_mode="compile",
        **overrides,
    )
    return TestClient(create_app(settings), raise_server_exceptions=False)


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    with _client(tmp_path) as c:
        yield c


@pytest.mark.req("FR-U02", "NFR-01")
def test_naive_expires_at_is_a_422_not_a_500(client: TestClient) -> None:
    r = client.post(
        "/api/v1/links",
        json={"target_url": "https://example.com", "expires_at": "2099-01-01T00:00:00"},
        headers=H,
    )
    assert r.status_code == 422
    assert r.headers["content-type"].startswith("application/problem+json")


@pytest.mark.req("FR-U03", "NFR-01")
@pytest.mark.parametrize(
    "target",
    [
        "http://[64:ff9b::7f00:1]/",  # NAT64-embedded loopback
        "http://metadata/computeMetadata/v1/",  # single-label internal name
        "http://intranet/",
        "http://example..com/",
        "http://-bad-.com/",
    ],
)
def test_internal_and_malformed_hosts_are_rejected(target: str) -> None:
    with pytest.raises(ValidationError):
        validate_target_url(target, UrlPolicy())


@pytest.mark.req("FR-U02")
def test_internationalised_domain_is_accepted_as_punycode() -> None:
    assert validate_target_url("https://münchen.de/x", UrlPolicy()) == (
        "https://xn--mnchen-3ya.de/x"
    )


@pytest.mark.req("NFR-01")
def test_unsafe_correlation_id_is_replaced(client: TestClient) -> None:
    r = client.get("/health/live", headers={"X-Correlation-ID": "A" * 5000})
    assert len(r.headers["X-Correlation-ID"]) <= 64
    ok = client.get("/health/live", headers={"X-Correlation-ID": "abc-123"})
    assert ok.headers["X-Correlation-ID"] == "abc-123"


@pytest.mark.req("NFR-01", "FR-G09")
@pytest.mark.parametrize("key", ["impact", "policy_exceptions", "implement_receipt"])
def test_caller_cannot_seed_engine_owned_run_data(client: TestClient, key: str) -> None:
    r = client.post(
        "/api/v1/workflows",
        headers=H,
        json={"title": "t", "requirement": REQ, "scope": "greenfield", "data": {key: {}}},
    )
    assert r.status_code == 422


@pytest.mark.req("NFR-01")
def test_verify_targets_are_confined_to_the_repository(tmp_path: Path) -> None:
    outside = tmp_path / "test_evil.py"
    outside.write_text("def test_x():\n    pass\n")
    assert not _inside(REPO, str(outside))
    assert not _inside(REPO, "../" + outside.name)
    assert not _inside(REPO, "--rootdir=/")
    assert _inside(REPO, "tests/unit")


def _drive(client: TestClient, payload_at_design: dict[str, Any]) -> tuple[dict[str, Any], int]:
    run = client.post(
        "/api/v1/workflows",
        headers=H,
        json={"title": "t", "requirement": REQ, "scope": "greenfield"},
    ).json()
    rid, status = run["id"], 0
    for _ in range(8):
        run = client.get(f"/api/v1/workflows/{rid}", headers=H).json()
        if not run["open_gates"]:
            break
        gate = run["open_gates"][0]
        payload = payload_at_design if gate == "design_approval" else {}
        r = client.post(
            f"/api/v1/workflows/{rid}/gates/{gate}/decision",
            headers=H,
            json={"decision": "approve", "reason": "ok", "payload": payload},
        )
        status = r.status_code
        if status >= 400:
            break
    return client.get(f"/api/v1/workflows/{rid}", headers=H).json(), status


@pytest.mark.req("FR-G09")
def test_non_exceptionable_policy_cannot_be_waived(tmp_path: Path) -> None:
    with _client(tmp_path, demo_fault_policy_fail="SEC-001") as c:
        run, status = _drive(c, {"compensating_control": "trust me", "policies": ["SEC-001"]})
    assert status == 409
    assert run["state"] != "COMPLETED"


@pytest.mark.req("FR-G09")
@pytest.mark.parametrize(
    "expires_at",
    [
        "9999-12-31T00:00:00+00:00",
        (datetime.now(UTC) - timedelta(days=1)).isoformat(),
        "2099-01-01T00:00:00",
    ],
)
def test_exception_expiry_must_be_bounded_and_future(tmp_path: Path, expires_at: str) -> None:
    with _client(tmp_path) as c:
        _, status = _drive(
            c,
            {"compensating_control": "WAF rule", "policies": ["CHG-001"], "expires_at": expires_at},
        )
    assert status == 409
