# ADR-004: Random 7-character base62 short codes with bounded regeneration

## Status
Proposed (Gate 4 pending) — resolves AMB-01/AMB-02 (Gate 3).

## Context
Short codes must be unique, URL-safe, and not predictable (FR-U04). The
candidate decided at Gate 3 that the same URL produces a new code per request
and that dedupe is explicit via idempotency key (AMB-01).

## Decision Drivers
- Non-enumerability (security)
- Collision handling that cannot leave partial state
- Simplicity

## Options Considered
1. **Sequential ID encoded base62** — + no collisions; − enumerable, leaks volume.
2. **Hash of URL (truncated)** — + deterministic; − forces dedupe semantics
   rejected in AMB-01; − truncation collisions still need handling.
3. **Random base62 from `secrets`, 7 chars, retry on unique violation up to 5 times** —
   + unpredictable; + ~3.5×10¹² keyspace; − theoretical collision, handled.

## Decision
Option 3. Generation lives in `domain/codes.py`; the service catches the
unique-constraint error, regenerates, and after 5 attempts raises a
`PERMANENT` persistence error with no row written.

## Rationale
Unpredictable codes close the enumeration abuse case for free; bounded
regeneration keeps the failure mode explicit and testable.

## Consequences
- Positive: no coordination, no counters, works with any store.
- Negative: no vanity codes (EX-01).
- Testing: property test for alphabet/length; collision test with a stubbed generator.

## Risks and Mitigations
- Weak randomness → `secrets`, not `random`.

## Reversibility
Easy: generator is a one-function port.

## Traceability
FR-U04, FR-U09, AMB-01, AMB-02, NFR-01.

## Validation
`tests/unit/test_codes.py`, `tests/integration/test_create_collision.py`.
