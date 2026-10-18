# Run 01a1502f975b0396cfa14096ea — Demo: no decision within the gate timeout -> safe-stop

> Executed run export. Measurements are **demonstration data** from a local,
> single-process run with deterministic agents; not production statistics.

- Scope: `greenfield`  ·  State: `SAFE_STOPPED`  ·  Reason: GATE_TIMEOUT: design_approval received no decision within 1.0s
- Requirement version: 1  ·  Graph version: 1  ·  Policy version: 1.0.0
- Events: 17  ·  Decisions: 0  ·  Replans: 0

## Stages

| stage | owner | state | attempt | parallel group | fallback | depends on |
|---|---|---|---|---|---|---|
| ingest | agent | SUCCEEDED | 1 |  |  |  |
| quality_check | agent | SUCCEEDED | 1 |  |  | ingest |
| clarification | human | SKIPPED | 0 |  |  | quality_check |
| decompose | agent | SUCCEEDED | 1 |  |  | clarification |
| design | agent | SUCCEEDED | 1 |  |  | decompose |
| design_approval | human | READY | 0 |  |  | design |
| docs_draft | agent | PENDING | 0 | after:design_approval |  | design_approval |
| implement | agent | PENDING | 0 | after:design_approval |  | design_approval |
| test_plan | agent | PENDING | 0 | after:design_approval |  | design_approval |
| verify | agent | PENDING | 0 |  |  | implement, test_plan, docs_draft |
| security_review | agent | PENDING | 0 |  |  | verify |
| compliance_check | agent | PENDING | 0 |  |  | verify, security_review |
| policy_exception | human | PENDING | 0 |  |  | compliance_check |
| release_readiness | human | PENDING | 0 |  |  | policy_exception |
| summary | agent | PENDING | 0 |  |  | release_readiness |

## Human decisions

_none recorded_

## Policy evaluations

_none recorded_

## Metrics (demonstration)

- Stage success rate: 1.0  ·  failure rate: 0.0
- Retries: 0 (timeouts 0)  ·  fallbacks: 0  ·  compensations: 0  ·  safe-stops: 1  ·  replans: 0
- Recovered failures: 0  ·  unrecovered: 0 []
- Recovery durations (s): {}  ·  **MTTR: None s** (MTTR = total recovery duration across recovered failure events / number of recovered failure events; unrecovered failures are excluded from the denominator)
- Latency: end-to-end 1.269707 s = active 1.269707 s + human wait 0.0 s

## Event timeline

| seq | at | actor | kind | stage | attempt | result | reason |
|---|---|---|---|---|---|---|---|
| 1 | 2026-10-18T18:04:18.678295+00:00 | system | run_created |  |  | CREATED | scope=greenfield planner=sdlc |
| 2 | 2026-10-18T18:04:18.686306+00:00 | system | run_started |  |  | RUNNING |  |
| 3 | 2026-10-18T18:04:18.689246+00:00 | system | stage_ready | ingest |  | READY |  |
| 4 | 2026-10-18T18:04:18.692331+00:00 | agent | stage_started | ingest | 1 | RUNNING |  |
| 5 | 2026-10-18T18:04:18.700640+00:00 | agent | stage_succeeded | ingest | 1 | SUCCEEDED |  |
| 6 | 2026-10-18T18:04:18.703440+00:00 | system | stage_ready | quality_check |  | READY |  |
| 7 | 2026-10-18T18:04:18.706872+00:00 | agent | stage_started | quality_check | 1 | RUNNING |  |
| 8 | 2026-10-18T18:04:18.712588+00:00 | agent | stage_succeeded | quality_check | 1 | SUCCEEDED |  |
| 9 | 2026-10-18T18:04:18.715015+00:00 | system | stage_skipped | clarification |  | SKIPPED | condition 'quality_check.clarification_required' is false |
| 10 | 2026-10-18T18:04:18.719234+00:00 | system | stage_ready | decompose |  | READY |  |
| 11 | 2026-10-18T18:04:18.721858+00:00 | agent | stage_started | decompose | 1 | RUNNING |  |
| 12 | 2026-10-18T18:04:18.727137+00:00 | agent | stage_succeeded | decompose | 1 | SUCCEEDED |  |
| 13 | 2026-10-18T18:04:18.729674+00:00 | system | stage_ready | design |  | READY |  |
| 14 | 2026-10-18T18:04:18.731749+00:00 | agent | stage_started | design | 1 | RUNNING |  |
| 15 | 2026-10-18T18:04:18.737579+00:00 | agent | stage_succeeded | design | 1 | SUCCEEDED |  |
| 16 | 2026-10-18T18:04:18.742518+00:00 | system | gate_opened | design_approval |  | WAITING | architecture approval; API/schema changes must be acknowledged (CHG-002) |
| 17 | 2026-10-18T18:04:19.948002+00:00 | system | safe_stop |  |  | SAFE_STOPPED | GATE_TIMEOUT: design_approval received no decision within 1.0s |
