# Research: technology and approach evaluation

Date: 2026-10-18. Each item: question → options → selection → why → what would
change the decision. Material items are formalised as ADRs in `docs/adr/`.

## R1. Web framework (→ ADR-002)
Options: FastAPI, Flask, Django REST, Litestar.
Selected: **FastAPI**. Pydantic v2 models double as the contract source (OpenAPI
export), dependency injection keeps the planes separable, TestClient makes
contract tests cheap. Django is heavier than the domain warrants; Flask needs
add-ons for schema/OpenAPI; Litestar is comparable but less familiar to a
reviewer.
Revisit if: a UI or admin surface becomes in-scope.

## R2. Persistence (→ ADR-003)
Options: SQLite via SQLAlchemy; Postgres in Docker; in-memory dicts with
JSON snapshot files.
Selected: **SQLite + SQLAlchemy 2.x (sync)**. Real transactions and unique
constraints (needed for short-code and idempotency uniqueness and for the
concurrency requirement FR-U10), zero setup for the reviewer, and the
repository/store interfaces make a Postgres swap a configuration change.
In-memory dicts cannot demonstrate resume-after-restart honestly.
Revisit if: multi-process workers are introduced (SQLite write locking).

## R3. Short-code strategy (→ ADR-004)
Options: random base62 (7 chars); sequential ID encoded base62; hash of URL
truncated.
Selected: **random base62, 7 chars, `secrets` module**. 62^7 ≈ 3.5×10^12
keyspace; birthday-bound collisions negligible at assessment scale and
handled by bounded regeneration on unique violation. Sequential codes are
enumerable (security); hash codes force dedupe semantics the candidate
rejected in AMB-01.

## R4. Orchestration engine (→ ADR-005, ADR-006)
Options: hand-built DAG + scheduler; LangGraph; Temporal/Prefect; Celery
chains.
Selected: **hand-built**. The assessment grades the orchestration design;
a framework would hide the state machine, gates and replanning behind its own
abstractions and make "is this really non-linear?" unanswerable from the code.
Temporal/Prefect need servers (violates local-runnability). LangGraph is
LLM-oriented and would push toward non-deterministic agents (rejected in
AMB-08). Cost: ~1 day of engine work, accepted.
Concurrency: `ThreadPoolExecutor` — agents are I/O-light; a thread pool gives
real overlapping execution without an async rewrite of SQLAlchemy usage.

## R5. State persistence model (→ ADR-006)
Options: mutable rows only; full event sourcing; rows + append-only event log.
Selected: **rows for current state + append-only event log**. Rows make
queries simple; events give audit-grade history and allow reconstruction
(NFR-04). Full event sourcing (rebuild on every read) is unnecessary ceremony
for one process.

## R6. Human approval model (→ ADR-007)
Options: gates as engine flags; gates as graph nodes owned by `human`.
Selected: **gate-as-node**. A human gate is a stage with `owner=human` and no
agent; the scheduler cannot execute it, so bypass is impossible by
construction rather than by check. Decisions are first-class rows.

## R7. Retry / fallback / safe-stop (→ ADR-008)
Selected: explicit per-stage policies; exponential backoff with cap;
per-attempt timeout via `concurrent.futures` timeout; failure classification
by the agent (`TRANSIENT` / `PERMANENT`). Safe-stop is a terminal run state.
Rollback = inverse file operations recorded by the workspace; compensation =
a registered counteracting action for non-reversible effects.

## R8. Dynamic replanning (→ ADR-009)
Options: restart the run from scratch on change; mutate graph in place;
rebuild graph from context and diff.
Selected: **rebuild + diff + invalidate downstream closure**. Restarting
loses lineage and re-runs approved work; in-place mutation makes the "before"
unrecoverable. Diff yields an explicit replan event with both graphs.

## R9. Agents (→ ADR-010)
Options: LLM-backed agents; deterministic executors; hybrid.
Selected (Gate 3, AMB-08): **deterministic executors behind an `Agent`
protocol**, with a workspace for the implement stage so that apply/verify/
revert are real file operations and real pytest runs. An LLM adapter is a
backlog item with a defined interface.

## R10. Policy model (→ ADR-011)
Selected: a versioned in-code registry (`POLICY_VERSION`), each policy a
callable over `RunContext` returning an outcome. YAML/OPA rejected: an extra
language and runtime for eight rules buys nothing demonstrable.

## R11. Tooling
ruff (lint + format), mypy strict on `src/`, pytest with markers, pip-audit,
pip-licenses, Typer for CLI, structlog for JSON logs with bound context.
A `scripts/check.sh` runs the whole gate set; no CI service is assumed
(reviewer runs it locally), though a GitHub Actions workflow is included so
the repo shows green checks.
