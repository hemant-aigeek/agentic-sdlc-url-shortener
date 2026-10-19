"""NFR-09 / SC-03: no orphan requirements, tasks or tests — checked, not promised."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "traceability.py"


@pytest.mark.architecture
@pytest.mark.req("NFR-09", "SC-03")
def test_every_requirement_has_a_test_and_every_test_cites_a_known_id() -> None:
    spec = importlib.util.spec_from_file_location("traceability", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _, problems = module.build()
    assert not problems, "\n".join(problems)
