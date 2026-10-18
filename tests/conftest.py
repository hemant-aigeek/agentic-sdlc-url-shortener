"""Shared fixtures. Tests never touch data/; everything runs against in-memory SQLite."""

from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "req(*ids): requirement identifiers covered by the test")
