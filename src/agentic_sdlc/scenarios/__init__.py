"""Reviewer-replayable scenarios (SCN-A/B/C and the executed demonstrations).

A scenario is data: the requirement, its scope, the demonstration faults to
inject, and the *scripted human decisions* that the person running it makes
at each gate. Nothing here bypasses a gate — the script calls
``Engine.decide`` exactly as a human would through the CLI or API, and the
actor name passed on the command line is what gets recorded. Interactive
replay (``--no-decide``) stops at every gate and prints the command to run.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

GateContext = dict[str, Any]
PayloadFn = Callable[[GateContext], dict[str, Any]]


@dataclass(frozen=True)
class Decide:
    gate: str
    decision: str  # approve | reject | clarify
    reason: str
    payload: dict[str, Any] | PayloadFn = field(default_factory=dict)

    def resolve(self, gate_ctx: GateContext) -> dict[str, Any]:
        return self.payload(gate_ctx) if callable(self.payload) else dict(self.payload)


@dataclass(frozen=True)
class Run:
    max_batches: int | None = None


@dataclass(frozen=True)
class Restart:
    """Simulate a process restart: a fresh engine resumes from the persisted store."""


@dataclass(frozen=True)
class Wait:
    seconds: float


Step = Decide | Run | Restart | Wait


@dataclass(frozen=True)
class Scenario:
    name: str
    title: str
    scope: str
    requirement: str
    description: str
    expected_terminal: str
    settings: dict[str, Any] = field(default_factory=dict)
    steps: tuple[Step, ...] = ()


GREENFIELD_REQUIREMENT = (
    "Add a per-link analytics summary endpoint GET /api/v1/links/{code}/analytics/summary "
    "returning total redirects, first and last redirect time, and redirects per day. "
    "Unknown codes return 404. Expired links keep their analytics readable."
)
BROWNFIELD_REQUIREMENT = (
    "Expired links must return 410 Gone instead of the current 404, and analytics for "
    "expired links must remain readable."
)
AMBIGUOUS_REQUIREMENT = "Links should expire after a while and be reusable."


def _first_options(gate_ctx: GateContext) -> dict[str, Any]:
    """Clarification answers: pick the recorded decision for each detected ambiguity."""
    ambiguities = gate_ctx["context"]["upstream_outputs"]["quality_check"]["ambiguities"]
    chosen: dict[str, str] = {}
    for amb in ambiguities:
        if amb["kind"] == "undefined_quantity":
            chosen[amb["id"]] = "ttl_30d"
        elif amb["kind"] == "conflict":
            chosen[amb["id"]] = "reuse_never"
        else:
            chosen[amb["id"]] = amb["options"][0]["id"]
    return {"answers": chosen}


DESIGN_OK = Decide(
    "design_approval",
    "approve",
    "design stays inside existing module boundaries; API/schema change acknowledged",
    {"api_change_acknowledged": True},
)
RELEASE_OK = Decide(
    "release_readiness",
    "approve",
    "verification executed, policies evaluated, evidence exported",
)

SCENARIOS: dict[str, Scenario] = {
    "greenfield": Scenario(
        name="greenfield",
        title="SCN-A greenfield: per-link analytics summary endpoint",
        scope="greenfield",
        requirement=GREENFIELD_REQUIREMENT,
        description=(
            "A complete, consistent, testable requirement proceeds without a clarification "
            "gate (the reason is recorded), fans out implement/test_plan/docs_draft in "
            "parallel, and recovers from two injected transient verify failures by bounded "
            "retry."
        ),
        expected_terminal="COMPLETED / READY",
        settings={"demo_fault_verify_transient_failures": 2},
        steps=(Run(), DESIGN_OK, Run(), RELEASE_OK, Run()),
    ),
    "brownfield": Scenario(
        name="brownfield",
        title="SCN-B brownfield: expired links return 410 instead of 404",
        scope="brownfield",
        requirement=BROWNFIELD_REQUIREMENT,
        description=(
            "Impact analysis scans the real repository and completes before any change; "
            "change-control policy CHG-001 verifies the ordering; the regression targets it "
            "found are executed by verify."
        ),
        expected_terminal="COMPLETED / READY",
        settings={},
        steps=(Run(), DESIGN_OK, Run(), RELEASE_OK, Run()),
    ),
    "ambiguous": Scenario(
        name="ambiguous",
        title="SCN-C ambiguous: links expire 'after a while' and are 'reusable'",
        scope="auto",
        requirement=AMBIGUOUS_REQUIREMENT,
        description=(
            "Two HIGH ambiguities are detected; the run blocks at the clarification gate; the "
            "recorded human answers produce requirement v2 and a replan; the automated "
            "security review hits an injected permanent fault and falls back to a manual "
            "checklist; SEC-003 requests an exception; a human accepts it with a compensating "
            "control; release is READY WITH ACCEPTED LIMITATIONS."
        ),
        expected_terminal="COMPLETED / READY WITH ACCEPTED LIMITATIONS",
        settings={"demo_fault_security_permanent_failure": True},
        steps=(
            Run(),
            Decide(
                "clarification",
                "clarify",
                "expire 30 days after creation; short codes are never reused (FR-U04 stands)",
                _first_options,
            ),
            Run(),
            DESIGN_OK,
            Run(),
            Decide(
                "policy_exception",
                "approve",
                "manual security checklist completed; residual risk accepted for this run",
                {
                    "compensating_control": "manual security checklist reviewed and attached",
                    "scope": "this run only",
                },
            ),
            Run(),
            RELEASE_OK,
            Run(),
        ),
    ),
    "policy-fail": Scenario(
        name="policy-fail",
        title="Demo: forced mandatory policy failure (SEC-002) safe-stops the run",
        scope="greenfield",
        requirement=GREENFIELD_REQUIREMENT,
        description=(
            "A non-exceptionable mandatory policy is forced to FAIL; the run enters "
            "SAFE_STOPPED with POLICY_BLOCKED and release readiness is NOT READY."
        ),
        expected_terminal="SAFE_STOPPED / NOT READY",
        settings={"demo_fault_policy_fail": "SEC-002"},
        steps=(Run(), DESIGN_OK, Run()),
    ),
    "rejection": Scenario(
        name="rejection",
        title="Demo: release rejected -> change set rolled back",
        scope="greenfield",
        requirement=GREENFIELD_REQUIREMENT,
        description=(
            "The release owner rejects; downstream stages never run; the implement stage's "
            "change set is rolled back from the recorded inverse (true rollback)."
        ),
        expected_terminal="REJECTED",
        settings={},
        steps=(
            Run(),
            DESIGN_OK,
            Run(),
            Decide("release_readiness", "reject", "not this sprint; defer the endpoint"),
        ),
    ),
    "resume": Scenario(
        name="resume",
        title="Demo: interruption after one batch, resumed by a fresh engine",
        scope="greenfield",
        requirement=GREENFIELD_REQUIREMENT,
        description=(
            "The run is suspended after one batch; a new engine instance resumes from the "
            "persisted state without re-executing the completed stage."
        ),
        expected_terminal="COMPLETED / READY",
        settings={},
        steps=(Run(max_batches=1), Restart(), DESIGN_OK, Run(), RELEASE_OK, Run()),
    ),
    "gate-timeout": Scenario(
        name="gate-timeout",
        title="Demo: no decision within the gate timeout -> safe-stop",
        scope="greenfield",
        requirement=GREENFIELD_REQUIREMENT,
        description=(
            "With a 1-second gate timeout and no human decision, the next tick safe-stops "
            "the run with GATE_TIMEOUT instead of inferring approval."
        ),
        expected_terminal="SAFE_STOPPED / GATE_TIMEOUT",
        settings={"gate_timeout_s": 1.0},
        steps=(Run(), Wait(1.2), Run()),
    ),
}
