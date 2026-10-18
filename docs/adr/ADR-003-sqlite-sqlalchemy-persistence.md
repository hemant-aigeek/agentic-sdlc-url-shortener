# ADR-003: SQLite via SQLAlchemy behind repository/store interfaces

## Status
Accepted — 2026-10-18 (Gate 4, docs/approvals/GATE-4-architecture.md)

## Context
Short-code uniqueness (FR-U04), idempotency (FR-U09), concurrency (FR-U10),
and resume-after-restart (FR-O13, NFR-03) all need durable storage with real
constraints and transactions, with zero setup for the reviewer (NFR-12).

## Decision Drivers
- Zero-install for reviewers; works in CI and on Windows
- Real unique constraints and transactions
- Swappable without touching domain or orchestration code (NFR-07)

## Options Considered
1. **In-memory structures + JSON snapshot** — + trivial; − cannot honestly show
   constraints, crash-resume, or concurrency safety.
2. **Postgres in Docker** — + production-like; − adds Docker as a hard
   dependency; − no assessment value beyond SQLite for one process.
3. **SQLite (file) via SQLAlchemy 2.x, WAL mode, with `Protocol`-typed
   repositories and a `WorkflowStore` protocol** — + real constraints, +
   zero setup, + in-memory mode for fast tests; − single-writer; − no
   `SELECT … FOR UPDATE`.

## Decision
Option 3. Domain ports in `domain/ports.py`; orchestration port in
`orchestration/store.py`; SQLite implementations in `persistence/`.

## Rationale
SQLite gives every property the requirements need at this scale, and the
ports make the Postgres path a new module, not a refactor.

## Consequences
- Positive: tests run against `sqlite:///:memory:` with the same code path.
- Negative: write serialisation under heavy parallel orchestration; mitigated
  by short transactions and WAL; documented scaling path.
- Operational: `data/app.db`, created on first run; `schema_version` table.
- Testing: persistence tests cover unique violations and crash-resume.
- Governance: schema changes bump `schema_version` and need change-control approval (CHG-002 when API-visible).

## Risks and Mitigations
- `database is locked` under thread-pool writes → `timeout=30`, WAL, retries classified TRANSIENT.

## Reversibility
Easy: implement the two protocols for another engine; configuration selects it.

## Traceability
FR-U04, FR-U09, FR-U10, FR-U11, FR-O06, FR-O13, NFR-03, NFR-05, NFR-07.

## Validation
Persistence and resume tests; concurrency test creating N links in parallel.
