# Architecture Decision Records

| ADR | Title | Status |
|---|---|---|
| [001](ADR-001-modular-monolith-two-planes.md) | Modular monolith with separated application and control planes | Proposed |
| [002](ADR-002-python-fastapi-stack.md) | Python 3.12+ / FastAPI / Pydantic v2 | Proposed |
| [003](ADR-003-sqlite-sqlalchemy-persistence.md) | SQLite via SQLAlchemy behind repository/store interfaces | Proposed |
| [004](ADR-004-random-base62-short-codes.md) | Random 7-char base62 short codes with bounded regeneration | Proposed |
| [005](ADR-005-hand-built-dag-scheduler.md) | Hand-built dependency graph and tick scheduler with thread-pool parallelism | Proposed |
| [006](ADR-006-state-rows-plus-event-log.md) | Current-state rows plus append-only event log | Proposed |
| [007](ADR-007-gate-as-node-approval-model.md) | Human gates as graph nodes; decisions as first-class records | Proposed |
| [008](ADR-008-retry-fallback-safestop-compensation.md) | Per-stage retry/timeout/fallback; safe-stop terminal; rollback vs compensation rule | Proposed |
| [009](ADR-009-graph-diff-replanning.md) | Dynamic replanning by graph rebuild, diff and downstream invalidation | Proposed |
| [010](ADR-010-deterministic-agents-run-workspace.md) | Deterministic agents behind an Agent protocol; implementation in an isolated run workspace | Proposed |
| [011](ADR-011-versioned-policy-registry.md) | Versioned in-code policy registry with four outcomes and blocking semantics | Proposed |

An ADR becomes **Accepted** only by an explicit human decision recorded in
`docs/approvals/`. Superseding requires a new ADR and a replan of affected tasks.
