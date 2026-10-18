"""Versioned policy registry (FR-G06, FR-G07, ADR-011).

Policies are code so they are testable and reviewable in diffs; the version
is recorded on every run and every evaluation. A policy is *mandatory* when
a FAIL blocks progression and release readiness, and *exceptionable* when a
human may approve a scoped, expiring exception with a compensating control.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from agentic_sdlc.orchestration.events import EventKind
from agentic_sdlc.policy.model import Outcome, Policy

if TYPE_CHECKING:
    from agentic_sdlc.policy.evaluator import PolicyInput

POLICY_VERSION = "1.0.0"

# Shared with scripts/secret_scan.py so the repository check and the workflow
# check agree on what a secret looks like.
SECRET_PATTERNS: dict[str, re.Pattern[str]] = {
    "aws-access-key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "private-key-block": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "generic-api-key": re.compile(
        r"(?i)\b(?:api[_-]?key|secret[_-]?key|access[_-]?token)\b\s*[:=]\s*['\"][A-Za-z0-9_\-]{20,}['\"]"
    ),
    "github-token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "slack-token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
}

ALLOWED_LICENSES = {
    "MIT",
    "BSD",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "Apache-2.0",
    "ISC",
    "PSF-2.0",
    "MPL-2.0",
    "0BSD",
    "Unlicense",
}

VALIDATION_FILE = "domain/validation.py"
VALIDATION_MARKERS = ("ALLOWED_SCHEMES", "_BLOCKED_NETWORKS")


def _walk_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _walk_strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in _walk_strings(v)]
    return []


# --- security -------------------------------------------------------------------


def _sec_001(inp: PolicyInput) -> tuple[Outcome, str]:
    change_set = inp.artifacts.get("change_set")
    if not change_set:
        return Outcome.NOT_APPLICABLE, "no change set produced in this run"
    files: dict[str, str] = change_set.get("files", {})
    touched = [p for p in files if p.endswith(VALIDATION_FILE)]
    if not touched:
        return Outcome.PASS, "change set does not touch URL validation"
    for path in touched:
        content = files[path] or ""
        missing = [m for m in VALIDATION_MARKERS if m not in content]
        if missing:
            return Outcome.FAIL, f"{path} removes validation controls: {', '.join(missing)}"
    return Outcome.PASS, f"validation controls intact in {', '.join(touched)}"


def _sec_002(inp: PolicyInput) -> tuple[Outcome, str]:
    hits: list[str] = []
    for kind, content in inp.artifacts.items():
        for text in _walk_strings(content):
            for name, pattern in SECRET_PATTERNS.items():
                if pattern.search(text):
                    hits.append(f"{kind}:{name}")
    if hits:
        return Outcome.FAIL, "secret patterns in artifacts: " + ", ".join(sorted(set(hits)))
    return Outcome.PASS, f"no secret patterns in {len(inp.artifacts)} artifacts"


def _sec_003(inp: PolicyInput) -> tuple[Outcome, str]:
    kinds = [(e.kind, e.stage) for e in inp.events]
    if (EventKind.FALLBACK_USED, "security_review") in kinds:
        return (
            Outcome.EXCEPTION_REQUESTED,
            "automated security review fell back to manual review; a human must accept "
            "the residual risk with a compensating control",
        )
    if (EventKind.STAGE_SUCCEEDED, "security_review") in kinds:
        return Outcome.PASS, "automated security review completed"
    return Outcome.NOT_APPLICABLE, "security review has not run yet"


# --- compliance -------------------------------------------------------------------


def _cmp_001(inp: PolicyInput) -> tuple[Outcome, str]:
    started: dict[str, int] = {}
    finished: set[str] = set()
    opened: set[str] = set()
    decided: set[str] = set()
    for e in inp.events:
        if e.stage is None:
            continue
        if e.kind is EventKind.STAGE_STARTED:
            started[e.stage] = started.get(e.stage, 0) + 1
        elif e.kind in {
            EventKind.STAGE_SUCCEEDED,
            EventKind.STAGE_FAILED,
            EventKind.FALLBACK_USED,
            EventKind.RETRY_SCHEDULED,
            EventKind.STAGE_TIMED_OUT,
        }:
            finished.add(e.stage)
        elif e.kind is EventKind.GATE_OPENED:
            opened.add(e.stage)
        elif e.kind is EventKind.DECISION_RECORDED:
            decided.add(e.stage)
    # the stage being evaluated right now is legitimately still running
    current = inp.extra.get("current_stage")
    dangling = sorted(s for s in started if s not in finished and s != current)
    undecided = sorted(opened - decided)
    if dangling or undecided:
        return (
            Outcome.FAIL,
            f"stages without a recorded end: {dangling}; gates without a decision: {undecided}",
        )
    return Outcome.PASS, f"{len(started)} executed stages and {len(opened)} gates fully recorded"


def _cmp_002(inp: PolicyInput) -> tuple[Outcome, str]:
    bad = [
        e.seq
        for e in inp.events
        if not e.actor_type or not e.kind or e.at is None or (e.target is None and e.stage is None)
    ]
    if bad:
        return Outcome.FAIL, f"events missing actor/action/timestamp/target: seq {bad[:10]}"
    return Outcome.PASS, f"{len(inp.events)} audit events carry actor, action, timestamp and target"


# --- change control -------------------------------------------------------------------


def _chg_001(inp: PolicyInput) -> tuple[Outcome, str]:
    scope = inp.ctx.data.get("scope", inp.ctx.scope)
    if scope != "brownfield":
        return (
            Outcome.NOT_APPLICABLE,
            f"scope is {scope}; impact analysis is required for brownfield only",
        )
    impact_at = next(
        (
            e.seq
            for e in inp.events
            if e.kind is EventKind.STAGE_SUCCEEDED and e.stage == "impact_analysis"
        ),
        None,
    )
    implement_at = next(
        (e.seq for e in inp.events if e.kind is EventKind.STAGE_STARTED and e.stage == "implement"),
        None,
    )
    if implement_at is None:
        return Outcome.PASS, "implementation has not started"
    if impact_at is None or "impact_analysis" not in inp.artifacts:
        return Outcome.FAIL, "implementation started without an impact-analysis artifact"
    if impact_at > implement_at:
        return Outcome.FAIL, "impact analysis completed after implementation started"
    return Outcome.PASS, "impact analysis recorded before implementation"


def _chg_002(inp: PolicyInput) -> tuple[Outcome, str]:
    design = inp.ctx.outputs.get("design", {})
    if not design.get("api_or_schema_impact"):
        return Outcome.NOT_APPLICABLE, "design reports no API or schema impact"
    decisions = [d for d in inp.ctx.decisions if d.get("gate") == "design_approval"]
    if not decisions:
        return Outcome.PASS, "design approval pending"
    if decisions[-1].get("payload", {}).get("api_change_acknowledged") is True:
        return Outcome.PASS, "API/schema change acknowledged at design approval"
    return Outcome.FAIL, "design changes an API or schema but the approval did not acknowledge it"


# --- dependencies / audit (advisory) -------------------------------------------------------


def _dep_001(inp: PolicyInput) -> tuple[Outcome, str]:
    deps = inp.artifacts.get("design", {}).get("new_dependencies", [])
    if not deps:
        return Outcome.PASS, "no new dependencies declared"
    bad = [
        f"{d.get('name')} ({d.get('license')})"
        for d in deps
        if d.get("license") not in ALLOWED_LICENSES
    ]
    if bad:
        return Outcome.FAIL, "licences outside allow-list: " + ", ".join(bad)
    return Outcome.PASS, f"{len(deps)} new dependencies allow-listed"


def _aud_001(inp: PolicyInput) -> tuple[Outcome, str]:
    retention = inp.ctx.data.get("audit_retention")
    if retention is None:
        return Outcome.FAIL, "audit retention setting not recorded in run context"
    return Outcome.PASS, f"audit retention recorded: {retention}"


POLICIES: list[Policy] = [
    Policy(
        "SEC-001",
        "security",
        "URL validation controls must not be weakened",
        True,
        False,
        POLICY_VERSION,
        _sec_001,
        "A change set touching domain/validation.py must keep the allow-list and blocked ranges.",
    ),
    Policy(
        "SEC-002",
        "security",
        "No secrets in workflow artifacts",
        True,
        False,
        POLICY_VERSION,
        _sec_002,
        "Artifacts are scanned with the same patterns as the repository secret scan.",
    ),
    Policy(
        "SEC-003",
        "security",
        "Automated security review completed",
        True,
        True,
        POLICY_VERSION,
        _sec_003,
        "If the automated review fell back to manual review, a human accepts the residual risk.",
    ),
    Policy(
        "CMP-001",
        "compliance",
        "Every executed stage and gate is fully recorded",
        True,
        False,
        POLICY_VERSION,
        _cmp_001,
    ),
    Policy(
        "CMP-002",
        "compliance",
        "Audit events carry actor, action, timestamp and target",
        True,
        False,
        POLICY_VERSION,
        _cmp_002,
    ),
    Policy(
        "CHG-001",
        "change-control",
        "Brownfield changes require impact analysis before implementation",
        True,
        True,
        POLICY_VERSION,
        _chg_001,
    ),
    Policy(
        "CHG-002",
        "change-control",
        "API/schema changes must be acknowledged at design approval",
        True,
        True,
        POLICY_VERSION,
        _chg_002,
    ),
    Policy(
        "DEP-001",
        "dependencies",
        "New dependencies use allow-listed licences",
        False,
        True,
        POLICY_VERSION,
        _dep_001,
    ),
    Policy(
        "AUD-001",
        "audit",
        "Audit retention is recorded for the run",
        False,
        True,
        POLICY_VERSION,
        _aud_001,
    ),
]


def get_policy(policy_id: str) -> Policy:
    for p in POLICIES:
        if p.id == policy_id:
            return p
    raise KeyError(policy_id)


def describe() -> list[dict[str, Any]]:
    return [p.describe() for p in POLICIES]
