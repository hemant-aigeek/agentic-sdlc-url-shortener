"""Plan §2 / CHG-002: the committed contract must match what the application serves."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "specs" / "001-agentic-url-shortener" / "contracts"

pytestmark = pytest.mark.contract


@pytest.mark.req("NFR-10")
def test_committed_contract_matches_application() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "export_contracts.py"), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.req("NFR-10")
def test_contract_is_versioned_and_covers_v1_routes() -> None:
    spec = yaml.safe_load((CONTRACTS / "openapi.yaml").read_text(encoding="utf-8"))
    paths = set(spec["paths"])
    assert {
        "/api/v1/links",
        "/api/v1/links/{code}",
        "/api/v1/links/{code}/analytics",
        "/{code}",
    } <= paths
    link_schema = spec["components"]["schemas"]["LinkResponse"]
    assert link_schema["x-schema-version"] == "1.0.0"
