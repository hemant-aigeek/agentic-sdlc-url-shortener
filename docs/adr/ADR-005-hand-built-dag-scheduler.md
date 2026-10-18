# ADR-005: Hand-built dependency graph and tick scheduler with thread-pool parallelism

## Status
Accepted — 2026-10-18 (Gate 4, docs/approvals/GATE-4-architecture.md)

## Context
The assignment's critical differentiator is an orchestration layer with an
explicit dependency graph, sequential and parallel paths with
synchronisation, entry/exit gates, and non-linear stateful execution
(FR-O02..O05, constitution II). The reviewer must be able to read the
mechanism from the code.

## Decision Drivers
- Transparency of the state machine and graph to a reviewer
- Local runnability (no servers)
- Deterministic, testable transitions
- Delivery within the timebox

## Options Considered
1. **Temporal / Prefect / Airflow** — + production-grade durability; − require
   a server; − hide the mechanism; − violate NFR-12.
2. **LangGraph** — + graph primitives, + checkpointing; − LLM-centric API that
   pulls toward non-deterministic agents (AMB-08 rejected); − "did you build
   orchestration or configure a library?" becomes a fair question.
3. **Celery canvas / asyncio.gather chains** — − linear chaining in disguise;
   no persisted graph, no gates.
4. **Hand-built: `WorkflowGraph` (nodes, edges, conditions, validation, ready-set,
   downstream closure, diff) + `Engine` tick loop + `ThreadPoolExecutor`** —
   + every property is explicit and unit-tested; − engine must be written (~1 day).

## Decision
Option 4. The engine is the deliverable; frameworks are listed in the
backlog as possible production hosts for the same graph model.

## Rationale
Owning the engine is the only way the "non-linear, stateful, governed"
claims can be verified by reading ~1,000 lines rather than trusting a library.

## Consequences
- Positive: transitions, gates, retries, replanning are all first-class and testable.
- Negative: no distributed durability; one process. Documented.
- Operational: `agentic-sdlc resume <run>` after restart.
- Testing: `tests/orchestration/` covers every transition and failure path.
- Governance: graph changes are plan/ADR-level changes.

## Risks and Mitigations
- Thread + SQLite contention → one session per stage execution, short transactions.
- Scheduler bugs → property-style tests on random DAGs for ready-set and closure.

## Reversibility
Medium: the graph model is framework-agnostic; an adapter to a workflow
engine is a backlog item.

## Traceability
FR-O01..O05, FR-O13, FR-O14, NFR-11; SC-04.

## Validation
Fan-out/join test shows overlapping stage intervals; evidence export of SCN-A.
