# ADR-011: Versioned in-code policy registry with four outcomes and blocking semantics

## Status
Proposed (Gate 4 pending)

## Context
FR-G06..G10 and constitution VI require versioned policies, four outcomes,
blocking on mandatory FAIL, approved exceptions with expiry and compensating
controls, and release readiness that fails on violations.

## Options Considered
OPA/Rego (rejected: extra runtime for eight rules); YAML rules with a mini
interpreter (rejected: a DSL to maintain); **Python registry**:
`POLICY_VERSION`, `Policy(id, domain, mandatory, check: Callable[[RunContext], Outcome])`.

## Decision
Python registry. Evaluated at `compliance_check` and again at
`release_readiness`. Outcomes `PASS | FAIL | EXCEPTION-REQUESTED |
NOT-APPLICABLE`. Mandatory FAIL → `policy_exception` gate; approved,
unexpired exception with compensating control → treated as PASS-with-
exception; otherwise safe-stop / `NOT READY`. Every evaluation row records
the policy version.

## Consequences
- Positive: policies are unit-testable functions; version bumps are commits.
- Negative: no hot reload (irrelevant).

## Traceability
FR-G06..G10, NFR-10, SC-06.

## Validation
`tests/unit/test_policies.py`; release-readiness `NOT READY` evidence.
