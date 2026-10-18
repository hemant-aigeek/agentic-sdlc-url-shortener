# ADR-007: Human gates as graph nodes; decisions as first-class records

## Status
Proposed (Gate 4 pending) — resolves AMB-06, AMB-09.

## Context
Mandatory approval gates must be impossible to skip, silence must never
approve, and every decision needs actor/time/reason (FR-G01..G05, NFR-11,
constitution III).

## Options Considered
1. **Flags checked by the engine before certain stages** — bypassable by a
   config error or a missed check.
2. **Gates as stages with `owner=human`** — the scheduler only executes
   `owner=agent` stages, so a gate blocks structurally; `Engine.decide` is the
   single transition out.

## Decision
Option 2. Gates: `clarification` (conditional), `design_approval`,
`release_readiness`, and dynamic `policy_exception` / `risk_acceptance`.
Identity: API key + `X-Actor` header (Gate 3, AMB-06). Timeout per gate,
default none; on timeout → `SAFE_STOPPED(GATE_TIMEOUT)` (AMB-09).
Decisions: `approve` | `reject` | `clarify` with reason and payload; rejection
triggers compensation and ends in `REJECTED` unless `return_to` names a stage.

## Rationale
Structural enforcement is simpler to verify than procedural checks and
matches the constitution's "cannot be disabled by configuration".

## Consequences
- Positive: gate status visible in the graph view; approvals are rows and events.
- Negative: no real identity provider; documented assumption.
- Testing: bypass attempts, timeout → safe-stop, rejection → compensation.

## Risks and Mitigations
- Actor spoofing → acknowledged limitation; production recommendation: OIDC.

## Reversibility
Easy to strengthen identity; gate model unchanged.

## Traceability
FR-G01..G05, FR-O12, NFR-11, SC-05.

## Validation
`tests/orchestration/test_gates.py`; SCN-B/C decision records in evidence.
