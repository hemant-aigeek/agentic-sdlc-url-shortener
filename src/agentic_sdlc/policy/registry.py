"""Versioned policy registry (FR-G06, ADR-011).

``POLICY_VERSION`` is recorded on every run and every evaluation. Policies are
defined in task group G7; the version constant exists from the start so the
control plane never evaluates against an unversioned policy set.
"""

from __future__ import annotations

POLICY_VERSION = "1.0.0"
