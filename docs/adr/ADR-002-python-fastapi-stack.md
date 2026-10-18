# ADR-002: Python 3.12+ with FastAPI and Pydantic v2

## Status
Proposed (Gate 4 pending) — technology choice made by the candidate at Gate 3.

## Context
A language and web framework were deliberately left open in the
specification. The candidate must defend the choice in a follow-up
interview, so familiarity and speed-to-evidence matter as much as fit.

## Decision Drivers
- Speed to a runnable, testable prototype
- Contract-first HTTP API with exportable OpenAPI (plan §2)
- Strong typing for the state machine and policies
- Reviewer friendliness (common runtime, no build step)

## Options Considered
1. **Python + FastAPI** — + Pydantic models are the contract; + TestClient;
   + rich testing ecosystem; − GIL limits CPU parallelism (irrelevant: agents are I/O-light).
2. **TypeScript + NestJS** — + decorators/DI; − more boilerplate; − needs a
   build step; − the candidate's deeper strength is Python for this kind of system.
3. **Go + chi** — + static binary; − slower to write the engine and tests in the timebox.

## Decision
Python ≥ 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x, Typer, structlog, pytest.

## Rationale
Best ratio of delivered evidence per hour for this candidate, and every
artifact a reviewer wants (OpenAPI, JSON schemas, typed state enums) falls
out of the stack rather than being hand-maintained.

## Consequences
- Positive: contract export and drift test are trivial; mypy strict is feasible.
- Negative: thread-pool parallelism rather than true multi-core (acceptable).
- Operational: `pip install -e .[dev]` is the whole setup.
- Testing: pytest markers drive traceability.
- Governance: dependency licences checked by DEP-001.

## Risks and Mitigations
- Version drift on reviewer machine → `requires-python >=3.12`, lock-free but pinned minimums; verified on 3.12 and 3.13.

## Reversibility
Hard (full rewrite) — accepted for an assessment prototype.

## Traceability
NFR-08, NFR-09, NFR-12; Gate 3 record; plan §Technical Context.

## Validation
`scripts/check.sh` green on a clean clone.
