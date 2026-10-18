"""NFR-06: redirect latency demonstration measurement (local, in-process, not production)."""

from __future__ import annotations

import statistics
import time
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from agentic_sdlc.api.app import create_app
from agentic_sdlc.config import Settings

pytestmark = pytest.mark.integration


@pytest.fixture
def client(tmp_path: Any) -> Iterator[TestClient]:
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        api_key="k",
        data_dir=tmp_path,
        rate_limit_capacity=10_000,
        rate_limit_refill_per_second=10_000,
        log_json=False,
    )
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.mark.req("NFR-06")
def test_redirect_p95_under_target_locally(client: TestClient) -> None:
    code = client.post(
        "/api/v1/links", json={"target_url": "https://example.com/x"}, headers={"X-API-Key": "k"}
    ).json()["code"]
    samples: list[float] = []
    for _ in range(200):
        started = time.perf_counter()
        r = client.get(f"/{code}", follow_redirects=False)
        samples.append((time.perf_counter() - started) * 1000)
        assert r.status_code == 307
    p95 = statistics.quantiles(samples, n=20)[-1]
    # AS-02: 50 ms p95 is a proposed local demonstration target, not a production SLO
    assert p95 < 50, f"p95 {p95:.2f} ms"
