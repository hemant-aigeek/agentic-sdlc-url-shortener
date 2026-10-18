"""Requirement-side agents: ingest, quality check, revision (FR-O15, SCN-A/C, ADR-010).

These agents are deterministic on purpose. They derive structure from the
requirement text with explicit, reviewable rules — sentence splitting, scope
cues, vagueness and conflict vocabularies, boundary checks against the
specification's exclusions — and record *why* they reached a verdict so the
quality decision is auditable rather than asserted. An LLM-backed agent
would implement the same interface and emit the same artifact shapes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from agentic_sdlc.config import Settings
from agentic_sdlc.errors import StageError
from agentic_sdlc.orchestration.agents.base import Agent, StageResult
from agentic_sdlc.orchestration.context import RunContext

# --- vocabularies (reviewable rules, not magic) -------------------------------------

BROWNFIELD_CUES = (
    "instead of",
    "currently",
    "existing",
    "current ",
    "change ",
    "fix ",
    "bug",
    "refactor",
    "replace",
    "must remain",
    "no longer",
    "rename",
    "migrate",
)
GREENFIELD_CUES = ("add ", "new ", "introduce", "create ", "support ", "expose ")

# phrase -> (ambiguity kind, question, options)
VAGUE_QUANTITIES: dict[str, tuple[str, list[dict[str, str]]]] = {
    "a while": (
        "How long after creation should a link expire?",
        [
            {"id": "ttl_30d", "label": "30 days after creation", "impact": "default TTL field"},
            {
                "id": "ttl_explicit",
                "label": "Only when the client sets expires_at",
                "impact": "no default; existing FR-U06 behaviour",
            },
            {
                "id": "ttl_config",
                "label": "Configurable default TTL",
                "impact": "new setting + migration of existing rows",
            },
        ],
    ),
    "some time": (
        "What is the exact duration?",
        [{"id": "fixed", "label": "A fixed duration (state it)", "impact": "testable TTL"}],
    ),
    "soon": (
        "What is the exact latency or time bound?",
        [{"id": "bound", "label": "A numeric bound", "impact": "measurable NFR"}],
    ),
    "quickly": (
        "What latency target is required?",
        [{"id": "p95", "label": "A p95 latency target", "impact": "benchmark + NFR"}],
    ),
    "fast": (
        "What latency target is required?",
        [{"id": "p95", "label": "A p95 latency target", "impact": "benchmark + NFR"}],
    ),
    "eventually": (
        "What consistency window is acceptable?",
        [{"id": "window", "label": "A bounded window", "impact": "testable analytics lag"}],
    ),
    "appropriate": (
        "What concrete rule defines 'appropriate'?",
        [{"id": "rule", "label": "An explicit rule", "impact": "testable acceptance criterion"}],
    ),
    "etc": (
        "Which items exactly are in scope?",
        [{"id": "enumerate", "label": "An explicit list", "impact": "bounded scope"}],
    ),
    "tbd": (
        "What is the decided value?",
        [{"id": "decide", "label": "A decided value", "impact": "unblocks implementation"}],
    ),
}

# phrase -> conflicting requirement id and the conflict statement
CONFLICTS: dict[str, tuple[str, str, list[dict[str, str]]]] = {
    "reusable": (
        "FR-U04",
        "'reusable' conflicts with short-code uniqueness (FR-U04): a code is never reassigned",
        [
            {
                "id": "reuse_never",
                "label": "Codes are never reused; expired codes return 410",
                "impact": "no change to FR-U04",
            },
            {
                "id": "reuse_after_expiry",
                "label": "Expired codes may be reassigned after a grace period",
                "impact": "weakens FR-U04; needs grace-period rule, analytics split per assignment",
            },
            {
                "id": "reuse_means_reactivate",
                "label": "'Reusable' means the owner can extend expiry",
                "impact": "new PATCH endpoint; API/schema change",
            },
        ],
    ),
    "predictable": (
        "FR-U04",
        "'predictable' codes conflict with FR-U04 (codes must not be predictable)",
        [{"id": "keep_random", "label": "Keep random codes", "impact": "none"}],
    ),
}

# specification exclusions (spec §11) that put a requirement out of boundary
EXCLUSIONS: dict[str, str] = {
    "account": "EX-01 user accounts / multi-tenancy are excluded",
    "login": "EX-01 user accounts / multi-tenancy are excluded",
    "tenant": "EX-01 user accounts / multi-tenancy are excluded",
    "vanity": "EX-01 custom aliases are excluded",
    "custom alias": "EX-01 custom aliases are excluded",
    "kafka": "EX-02 message brokers are excluded",
    "rabbitmq": "EX-02 message brokers are excluded",
    "deploy to": "EX-04 production deployment is excluded",
    "dashboard": "EX-05 UI beyond API documentation is excluded",
    "ui ": "EX-05 UI beyond API documentation is excluded",
}

TESTABILITY_CUES = (
    "return",
    "respond",
    "reject",
    "must",
    "should",
    "status",
    "endpoint",
    "record",
    "expire",
    "redirect",
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


_MODAL = re.compile(r"\b(must|should|shall|returns?|reject|keep|remain)\b", re.IGNORECASE)
_CLAUSE_SPLIT = re.compile(r",\s+and\s+|;\s+")


def _sentences(text: str) -> list[str]:
    """Split into statements: sentences, then compound clauses that each carry a modal."""
    cleaned = " ".join(text.split())
    parts = [p.strip() for p in _SENTENCE_SPLIT.split(cleaned) if p.strip()]
    out: list[str] = []
    for part in parts or [cleaned]:
        clauses = [c.strip() for c in _CLAUSE_SPLIT.split(part) if c.strip()]
        if len(clauses) > 1 and all(_MODAL.search(c) for c in clauses):
            out.extend(c if c.endswith((".", "!", "?")) else c + "." for c in clauses)
        else:
            out.append(part)
    return out


def _classify_scope(text: str) -> tuple[str, list[str]]:
    lower = f" {text.lower()} "
    brown = [c for c in BROWNFIELD_CUES if c in lower]
    green = [c for c in GREENFIELD_CUES if c in lower]
    if brown and (not green or len(brown) >= len(green)):
        return "brownfield", brown
    if green:
        return "greenfield", green
    return "greenfield", ["no scope cue found; defaulting to greenfield"]


def _acceptance_criteria(statements: list[str]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for i, s in enumerate(statements, start=1):
        out.append(
            {
                "id": f"AC-{i:02d}",
                "statement": s,
                "observable": _observable(s),
            }
        )
    return out


def _observable(statement: str) -> str:
    lower = statement.lower()
    if re.search(r"\b(4\d\d|5\d\d|2\d\d|3\d\d)\b", lower):
        code = re.search(r"\b([2-5]\d\d)\b", lower)
        return f"HTTP response status is {code.group(1) if code else 'as stated'}"
    if "endpoint" in lower or "get " in lower or "post " in lower:
        return "endpoint exists in the OpenAPI contract and returns the stated fields"
    if "expire" in lower:
        return "an expired link is not redirected; its status is observable"
    if "analytics" in lower:
        return "analytics response reflects the stated counts"
    return "behaviour is observable through the HTTP API or a test"


@dataclass
class IngestAgent(Agent):
    settings: Settings
    name: str = "ingest"

    def execute(self, ctx: RunContext, stage: str, attempt: int) -> StageResult:
        text = ctx.requirement_raw.strip()
        if not text:
            raise StageError("empty requirement")
        statements = _sentences(text)
        classified, cues = _classify_scope(text)
        if ctx.scope in {"greenfield", "brownfield", "ambiguous"}:
            scope, source = ctx.scope, "explicit"
        else:
            scope, source = classified, "classified"
        constraints = [s for s in statements if re.search(r"\bmust (not|remain)\b", s.lower())]
        normalized: dict[str, Any] = {
            "version": ctx.requirement_version,
            "title": ctx.title or statements[0][:80],
            "intent": statements[0],
            "scope": scope,
            "scope_source": source,
            "scope_cues": cues,
            "classified_scope": classified,
            "functional_statements": statements,
            "constraints": constraints,
            "acceptance_criteria": _acceptance_criteria(statements),
            "source": "requirement_raw",
        }
        retention = (
            "life of the local store"
            if self.settings.audit_retention_days is None
            else f"{self.settings.audit_retention_days} days"
        )
        return StageResult(
            output={
                "scope": scope,
                "scope_source": source,
                "statements": len(statements),
                "acceptance_criteria": len(normalized["acceptance_criteria"]),
            },
            artifacts=[("normalized_requirement", normalized)],
            data_updates={"normalized": normalized, "scope": scope, "audit_retention": retention},
        )


def detect_ambiguities(statements: list[str]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    n = 0
    for s in statements:
        lower = f" {s.lower()} "
        for phrase, (question, options) in VAGUE_QUANTITIES.items():
            if f" {phrase} " in lower or f" {phrase}," in lower or f" {phrase}." in lower:
                n += 1
                found.append(
                    {
                        "id": f"AMB-R{n}",
                        "kind": "undefined_quantity",
                        "severity": "HIGH",
                        "phrase": phrase,
                        "statement": s,
                        "question": question,
                        "options": options,
                    }
                )
        for phrase, (req, why, options) in CONFLICTS.items():
            if phrase in lower:
                n += 1
                found.append(
                    {
                        "id": f"AMB-R{n}",
                        "kind": "conflict",
                        "severity": "HIGH",
                        "phrase": phrase,
                        "statement": s,
                        "conflicts_with": req,
                        "question": why + " — which interpretation applies?",
                        "options": options,
                    }
                )
        if "?" in s or "??" in s:
            n += 1
            found.append(
                {
                    "id": f"AMB-R{n}",
                    "kind": "open_question",
                    "severity": "MEDIUM",
                    "phrase": "?",
                    "statement": s,
                    "question": "The requirement contains an open question; what is the answer?",
                    "options": [{"id": "answer", "label": "Provide the answer", "impact": "-"}],
                }
            )
    return found


def run_checks(normalized: dict[str, Any], ambiguities: list[dict[str, Any]]) -> dict[str, Any]:
    statements: list[str] = normalized["functional_statements"]
    text = " ".join(statements).lower()
    testable = [s for s in statements if any(c in s.lower() for c in TESTABILITY_CUES)]
    boundary_hits = [why for cue, why in EXCLUSIONS.items() if cue in f" {text} "]
    return {
        "completeness": {
            "passed": len(statements) >= 1 and bool(normalized["acceptance_criteria"]),
            "detail": f"{len(statements)} statements, "
            f"{len(normalized['acceptance_criteria'])} acceptance criteria derived",
        },
        "consistency": {
            "passed": not any(a["kind"] == "conflict" for a in ambiguities),
            "detail": "no conflicts with approved requirements"
            if not any(a["kind"] == "conflict" for a in ambiguities)
            else "; ".join(a["question"] for a in ambiguities if a["kind"] == "conflict"),
        },
        "testability": {
            "passed": len(testable) == len(statements),
            "detail": f"{len(testable)}/{len(statements)} statements have an observable outcome",
        },
        "boundaries": {
            "passed": not boundary_hits,
            "detail": "within approved scope" if not boundary_hits else "; ".join(boundary_hits),
        },
    }


def _max_severity(ambiguities: list[dict[str, Any]]) -> str:
    order = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}
    return max((a["severity"] for a in ambiguities), key=lambda s: order[s], default="NONE")


@dataclass
class QualityCheckAgent(Agent):
    settings: Settings
    name: str = "quality_check"

    def execute(self, ctx: RunContext, stage: str, attempt: int) -> StageResult:
        normalized = ctx.data.get("normalized")
        if not normalized:
            raise StageError("quality_check requires the normalized requirement from ingest")
        ambiguities = detect_ambiguities(normalized["functional_statements"])
        checks = run_checks(normalized, ambiguities)
        severity = _max_severity(ambiguities)
        failed = [k for k, v in checks.items() if not v["passed"]]
        required = severity == "HIGH" or bool(failed)
        if required:
            reason = (
                f"clarification required: max ambiguity severity {severity}; failed checks: "
                f"{failed or 'none'}"
            )
        else:
            reason = (
                "no clarification needed: all requirement-quality checks passed "
                f"(completeness, consistency, testability, boundaries); "
                f"max ambiguity severity {severity}"
            )
        output = {
            "ambiguities": ambiguities,
            "max_severity": severity,
            "checks": checks,
            "failed_checks": failed,
            "clarification_required": required,
            "reason_no_clarification": reason if not required else "",
            "reason": reason,
            "requirement_version": ctx.requirement_version,
        }
        return StageResult(
            output=output,
            artifacts=[("quality_check", output)],
            data_updates={"clarification_required": required, "quality_reason": reason},
        )


@dataclass
class RequirementRevisionAgent(Agent):
    """Folds human clarification answers into a new requirement version (FR-O14)."""

    settings: Settings
    name: str = "requirement_revision"

    def execute(self, ctx: RunContext, stage: str, attempt: int) -> StageResult:
        normalized = dict(ctx.data.get("normalized") or {})
        quality = ctx.output("quality_check")
        if not normalized or not quality:
            raise StageError("requirement_revision requires ingest and quality_check outputs")
        clarifications: list[dict[str, Any]] = ctx.data.get("clarifications", [])
        answers: dict[str, Any] = {}
        for c in clarifications:
            answers.update(c.get("answers", {}))
        resolved: list[dict[str, Any]] = []
        remaining: list[dict[str, Any]] = []
        for amb in quality.get("ambiguities", []):
            answer = answers.get(amb["id"])
            if answer is None:
                if amb["severity"] == "HIGH":
                    remaining.append(amb)
                continue
            label = next((o["label"] for o in amb["options"] if o["id"] == answer), str(answer))
            resolved.append(
                {
                    "ambiguity": amb["id"],
                    "kind": amb["kind"],
                    "phrase": amb["phrase"],
                    "answer": label,
                    "answer_id": answer,
                    "replaces": amb["statement"],
                }
            )
        if remaining:
            raise StageError(
                "unresolved HIGH ambiguities after clarification: "
                + ", ".join(a["id"] for a in remaining)
            )
        statements = []
        for s in normalized["functional_statements"]:
            notes = [f"{r['ambiguity']}: {r['answer']}" for r in resolved if r["replaces"] == s]
            statements.append(f"{s} [resolved {'; '.join(notes)}]" if notes else s)
        revised = {
            **normalized,
            "version": ctx.requirement_version,
            "functional_statements": statements,
            "acceptance_criteria": _acceptance_criteria(statements)
            + [
                {
                    "id": f"AC-C{i}",
                    "statement": r["answer"],
                    "observable": "clarified behaviour is covered by a test",
                }
                for i, r in enumerate(resolved, start=1)
            ],
            "resolved_ambiguities": resolved,
            "source": "clarification",
        }
        recheck = detect_ambiguities(statements)
        still_high = [
            a
            for a in recheck
            if a["severity"] == "HIGH" and a["phrase"] not in {r["phrase"] for r in resolved}
        ]
        output = {
            "requirement_version": ctx.requirement_version,
            "resolved": [r["ambiguity"] for r in resolved],
            "remaining_high_ambiguities": [a["id"] for a in still_high],
            "checks": run_checks(revised, still_high),
        }
        return StageResult(
            output=output,
            artifacts=[("normalized_requirement", revised), ("requirement_revision", output)],
            data_updates={"normalized": revised, "clarification_required": bool(still_high)},
        )
