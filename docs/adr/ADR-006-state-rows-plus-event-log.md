# ADR-006: Current-state rows plus append-only event log

## Status
Accepted — 2026-10-18 (Gate 4, docs/approvals/GATE-4-architecture.md)

## Context
State, context, artifact provenance, decisions and lineage must be persisted
and reconstructable (FR-O06, FR-O07, FR-O20, NFR-04, NFR-05, constitution IX).

## Options Considered
1. **Mutable rows only** — simple; no history; cannot audit.
2. **Full event sourcing** — complete history; every read rebuilds state; overkill for one process.
3. **Rows for current state + append-only `workflow_events` + versioned artifacts with `derived_from`** —
   simple queries, audit-grade history, reconstruction test possible.

## Decision
Option 3. No code path updates or deletes events; artifacts are never
overwritten, only versioned and flagged `invalidated`.

## Rationale
Reviewer can `GET /events` and replay; engine code stays readable.

## Consequences
- Positive: MTTR and metrics computed purely from events.
- Negative: duplication between rows and events (reconstruction test guards divergence).
- Governance: event kinds are a versioned contract (`contracts/schemas/event.json`).

## Risks and Mitigations
- Divergence → `tests/orchestration/test_reconstruction.py`.

## Reversibility
Easy toward full event sourcing; events already exist.

## Traceability
FR-O06, FR-O07, FR-O19, FR-O20, NFR-04, NFR-05.

## Validation
Reconstruction test; lineage endpoint walk in SCN-C evidence.
