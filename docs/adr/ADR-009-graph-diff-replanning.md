# ADR-009: Dynamic replanning by graph rebuild, diff and downstream invalidation

## Status
Proposed (Gate 4 pending)

## Context
FR-O14 requires re-planning when upstream outputs change without re-running
unaffected work or bypassing gates; SCN-C depends on it.

## Options Considered
1. Restart the run — loses approvals and lineage.
2. Mutate the graph in place — no "before" record.
3. **Rebuild from context, diff, invalidate downstream closure, version artifacts, record `ReplanEvent`.**

## Decision
Option 3. `planner.build_graph(ctx)` is pure; `graph.diff()` returns
added/removed/changed nodes; the engine marks the downstream closure of
changed nodes `INVALIDATED` (artifacts `invalidated=True`, new versions
created on re-execution), persists `ReplanEvent(before, after, reason)`,
bumps `graph_version`, re-arms downstream gates, and resumes.

## Consequences
- Positive: evidence shows both graphs and exactly which stages re-ran.
- Negative: planner must be deterministic given context (tested).

## Risks and Mitigations
- Over-invalidation → closure computed from changed nodes only; test asserts unaffected stages keep their artifact version.

## Reversibility
Easy.

## Traceability
FR-O14, FR-O07, SCN-C, SC-04.

## Validation
`tests/orchestration/test_replan.py`; SCN-C evidence.
