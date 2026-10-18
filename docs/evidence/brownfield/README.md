# Run 01a1502e31fc508fb3153c49e9 — SCN-B brownfield: expired links return 410 instead of 404

> Executed run export. Measurements are **demonstration data** from a local,
> single-process run with deterministic agents; not production statistics.

- Scope: `brownfield`  ·  State: `COMPLETED`
- Requirement version: 1  ·  Graph version: 1  ·  Policy version: 1.0.0
- Events: 45  ·  Decisions: 2  ·  Replans: 0

## Stages

| stage | owner | state | attempt | parallel group | fallback | depends on |
|---|---|---|---|---|---|---|
| ingest | agent | SUCCEEDED | 1 |  |  |  |
| quality_check | agent | SUCCEEDED | 1 |  |  | ingest |
| clarification | human | SKIPPED | 0 |  |  | quality_check |
| impact_analysis | agent | SUCCEEDED | 1 |  |  | clarification |
| decompose | agent | SUCCEEDED | 1 |  |  | impact_analysis |
| design | agent | SUCCEEDED | 1 |  |  | decompose |
| design_approval | human | SUCCEEDED | 0 |  |  | design |
| docs_draft | agent | SUCCEEDED | 1 | after:design_approval |  | design_approval |
| implement | agent | SUCCEEDED | 1 | after:design_approval |  | design_approval |
| test_plan | agent | SUCCEEDED | 1 | after:design_approval |  | design_approval |
| verify | agent | SUCCEEDED | 1 |  |  | implement, test_plan, docs_draft |
| security_review | agent | SUCCEEDED | 1 |  |  | verify |
| compliance_check | agent | SUCCEEDED | 1 |  |  | verify, security_review |
| policy_exception | human | SKIPPED | 0 |  |  | compliance_check |
| release_readiness | human | SUCCEEDED | 0 |  |  | policy_exception |
| summary | agent | SUCCEEDED | 1 |  |  | release_readiness |

## Human decisions

| gate | actor | decision | reason | at |
|---|---|---|---|---|
| design_approval | hemant | approve | design stays inside existing module boundaries; API/schema change acknowledged | 2026-10-18 18:02:47.335992+00:00 |
| release_readiness | hemant | approve | verification executed, policies evaluated, evidence exported | 2026-10-18 18:02:53.878432+00:00 |

## Policy evaluations

| policy | version | outcome | detail |
|---|---|---|---|
| SEC-001 | 1.0.0 | PASS | change set does not touch URL validation |
| SEC-002 | 1.0.0 | PASS | no secret patterns in 10 artifacts |
| SEC-003 | 1.0.0 | PASS | automated security review completed |
| CMP-001 | 1.0.0 | PASS | 11 executed stages and 1 gates fully recorded |
| CMP-002 | 1.0.0 | PASS | 37 audit events carry actor, action, timestamp and target |
| CHG-001 | 1.0.0 | PASS | impact analysis recorded before implementation |
| CHG-002 | 1.0.0 | PASS | API/schema change acknowledged at design approval |
| DEP-001 | 1.0.0 | PASS | no new dependencies declared |
| AUD-001 | 1.0.0 | PASS | audit retention recorded: life of the local store |

## Metrics (demonstration)

- Stage success rate: 1.0  ·  failure rate: 0.0
- Retries: 0 (timeouts 0)  ·  fallbacks: 0  ·  compensations: 0  ·  safe-stops: 0  ·  replans: 0
- Recovered failures: 0  ·  unrecovered: 0 []
- Recovery durations (s): {}  ·  **MTTR: None s** (MTTR = total recovery duration across recovered failure events / number of recovered failure events; unrecovered failures are excluded from the denominator)
- Latency: end-to-end 6.703098 s = active 6.691028 s + human wait 0.01207 s

## Event timeline

| seq | at | actor | kind | stage | attempt | result | reason |
|---|---|---|---|---|---|---|---|
| 1 | 2026-10-18T18:02:47.196377+00:00 | system | run_created |  |  | CREATED | scope=brownfield planner=sdlc |
| 2 | 2026-10-18T18:02:47.207944+00:00 | system | run_started |  |  | RUNNING |  |
| 3 | 2026-10-18T18:02:47.212314+00:00 | system | stage_ready | ingest |  | READY |  |
| 4 | 2026-10-18T18:02:47.216328+00:00 | agent | stage_started | ingest | 1 | RUNNING |  |
| 5 | 2026-10-18T18:02:47.225148+00:00 | agent | stage_succeeded | ingest | 1 | SUCCEEDED |  |
| 6 | 2026-10-18T18:02:47.228388+00:00 | system | stage_ready | quality_check |  | READY |  |
| 7 | 2026-10-18T18:02:47.231734+00:00 | agent | stage_started | quality_check | 1 | RUNNING |  |
| 8 | 2026-10-18T18:02:47.237274+00:00 | agent | stage_succeeded | quality_check | 1 | SUCCEEDED |  |
| 9 | 2026-10-18T18:02:47.239900+00:00 | system | stage_skipped | clarification |  | SKIPPED | condition 'quality_check.clarification_required' is false |
| 10 | 2026-10-18T18:02:47.241896+00:00 | system | stage_ready | impact_analysis |  | READY |  |
| 11 | 2026-10-18T18:02:47.244537+00:00 | agent | stage_started | impact_analysis | 1 | RUNNING |  |
| 12 | 2026-10-18T18:02:47.297534+00:00 | agent | stage_succeeded | impact_analysis | 1 | SUCCEEDED |  |
| 13 | 2026-10-18T18:02:47.300973+00:00 | system | stage_ready | decompose |  | READY |  |
| 14 | 2026-10-18T18:02:47.304516+00:00 | agent | stage_started | decompose | 1 | RUNNING |  |
| 15 | 2026-10-18T18:02:47.312137+00:00 | agent | stage_succeeded | decompose | 1 | SUCCEEDED |  |
| 16 | 2026-10-18T18:02:47.315238+00:00 | system | stage_ready | design |  | READY |  |
| 17 | 2026-10-18T18:02:47.318868+00:00 | agent | stage_started | design | 1 | RUNNING |  |
| 18 | 2026-10-18T18:02:47.326293+00:00 | agent | stage_succeeded | design | 1 | SUCCEEDED |  |
| 19 | 2026-10-18T18:02:47.330893+00:00 | system | gate_opened | design_approval |  | WAITING | architecture approval; API/schema changes must be acknowledged (CHG-002) |
| 20 | 2026-10-18T18:02:47.338275+00:00 | human | decision_recorded | design_approval |  | approve | design stays inside existing module boundaries; API/schema change acknowledged |
| 21 | 2026-10-18T18:02:47.348870+00:00 | system | stage_ready | docs_draft |  | READY |  |
| 22 | 2026-10-18T18:02:47.351126+00:00 | system | stage_ready | implement |  | READY |  |
| 23 | 2026-10-18T18:02:47.354114+00:00 | system | stage_ready | test_plan |  | READY |  |
| 24 | 2026-10-18T18:02:47.356766+00:00 | agent | stage_started | docs_draft | 1 | RUNNING |  |
| 25 | 2026-10-18T18:02:47.359720+00:00 | agent | stage_started | implement | 1 | RUNNING |  |
| 26 | 2026-10-18T18:02:47.361991+00:00 | agent | stage_started | test_plan | 1 | RUNNING |  |
| 27 | 2026-10-18T18:02:47.369284+00:00 | agent | stage_succeeded | docs_draft | 1 | SUCCEEDED |  |
| 28 | 2026-10-18T18:02:47.375136+00:00 | agent | stage_succeeded | test_plan | 1 | SUCCEEDED |  |
| 29 | 2026-10-18T18:02:47.379981+00:00 | agent | stage_succeeded | implement | 1 | SUCCEEDED |  |
| 30 | 2026-10-18T18:02:47.383024+00:00 | system | stage_ready | verify |  | READY |  |
| 31 | 2026-10-18T18:02:47.385853+00:00 | agent | stage_started | verify | 1 | RUNNING |  |
| 32 | 2026-10-18T18:02:53.836742+00:00 | agent | stage_succeeded | verify | 1 | SUCCEEDED |  |
| 33 | 2026-10-18T18:02:53.839462+00:00 | system | stage_ready | security_review |  | READY |  |
| 34 | 2026-10-18T18:02:53.841921+00:00 | agent | stage_started | security_review | 1 | RUNNING |  |
| 35 | 2026-10-18T18:02:53.847722+00:00 | agent | stage_succeeded | security_review | 1 | SUCCEEDED |  |
| 36 | 2026-10-18T18:02:53.849932+00:00 | system | stage_ready | compliance_check |  | READY |  |
| 37 | 2026-10-18T18:02:53.852425+00:00 | agent | stage_started | compliance_check | 1 | RUNNING |  |
| 38 | 2026-10-18T18:02:53.869509+00:00 | agent | stage_succeeded | compliance_check | 1 | SUCCEEDED |  |
| 39 | 2026-10-18T18:02:53.871879+00:00 | system | stage_skipped | policy_exception |  | SKIPPED | condition 'compliance_check.blocking non-empty' is false |
| 40 | 2026-10-18T18:02:53.874726+00:00 | system | gate_opened | release_readiness |  | WAITING | human release-readiness decision on the computed evidence |
| 41 | 2026-10-18T18:02:53.879414+00:00 | human | decision_recorded | release_readiness |  | approve | verification executed, policies evaluated, evidence exported |
| 42 | 2026-10-18T18:02:53.886707+00:00 | system | stage_ready | summary |  | READY |  |
| 43 | 2026-10-18T18:02:53.888987+00:00 | agent | stage_started | summary | 1 | RUNNING |  |
| 44 | 2026-10-18T18:02:53.897163+00:00 | agent | stage_succeeded | summary | 1 | SUCCEEDED |  |
| 45 | 2026-10-18T18:02:53.899475+00:00 | system | run_completed |  |  | COMPLETED | all stages done |
