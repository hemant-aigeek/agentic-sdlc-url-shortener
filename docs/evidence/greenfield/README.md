# Run 01a1502e01bb9f20673485e06a — SCN-A greenfield: per-link analytics summary endpoint

> Executed run export. Measurements are **demonstration data** from a local,
> single-process run with deterministic agents; not production statistics.

- Scope: `greenfield`  ·  State: `COMPLETED`
- Requirement version: 1  ·  Graph version: 1  ·  Policy version: 1.0.0
- Events: 50  ·  Decisions: 2  ·  Replans: 0

## Stages

| stage | owner | state | attempt | parallel group | fallback | depends on |
|---|---|---|---|---|---|---|
| ingest | agent | SUCCEEDED | 1 |  |  |  |
| quality_check | agent | SUCCEEDED | 1 |  |  | ingest |
| clarification | human | SKIPPED | 0 |  |  | quality_check |
| decompose | agent | SUCCEEDED | 1 |  |  | clarification |
| design | agent | SUCCEEDED | 1 |  |  | decompose |
| design_approval | human | SUCCEEDED | 0 |  |  | design |
| docs_draft | agent | SUCCEEDED | 1 | after:design_approval |  | design_approval |
| implement | agent | SUCCEEDED | 1 | after:design_approval |  | design_approval |
| test_plan | agent | SUCCEEDED | 1 | after:design_approval |  | design_approval |
| verify | agent | SUCCEEDED | 3 |  |  | implement, test_plan, docs_draft |
| security_review | agent | SUCCEEDED | 1 |  |  | verify |
| compliance_check | agent | SUCCEEDED | 1 |  |  | verify, security_review |
| policy_exception | human | SKIPPED | 0 |  |  | compliance_check |
| release_readiness | human | SUCCEEDED | 0 |  |  | policy_exception |
| summary | agent | SUCCEEDED | 1 |  |  | release_readiness |

## Human decisions

| gate | actor | decision | reason | at |
|---|---|---|---|---|
| design_approval | hemant | approve | design stays inside existing module boundaries; API/schema change acknowledged | 2026-10-18 18:02:34.897145+00:00 |
| release_readiness | hemant | approve | verification executed, policies evaluated, evidence exported | 2026-10-18 18:02:40.222881+00:00 |

## Policy evaluations

| policy | version | outcome | detail |
|---|---|---|---|
| SEC-001 | 1.0.0 | PASS | change set does not touch URL validation |
| SEC-002 | 1.0.0 | PASS | no secret patterns in 9 artifacts |
| SEC-003 | 1.0.0 | PASS | automated security review completed |
| CMP-001 | 1.0.0 | PASS | 10 executed stages and 1 gates fully recorded |
| CMP-002 | 1.0.0 | PASS | 42 audit events carry actor, action, timestamp and target |
| CHG-001 | 1.0.0 | NOT-APPLICABLE | scope is greenfield; impact analysis is required for brownfield only |
| CHG-002 | 1.0.0 | PASS | API/schema change acknowledged at design approval |
| DEP-001 | 1.0.0 | PASS | no new dependencies declared |
| AUD-001 | 1.0.0 | PASS | audit retention recorded: life of the local store |

## Metrics (demonstration)

- Stage success rate: 1.0  ·  failure rate: 0.0
- Retries: 2 (timeouts 0)  ·  fallbacks: 0  ·  compensations: 0  ·  safe-stops: 0  ·  replans: 0
- Recovered failures: 1  ·  unrecovered: 0 []
- Recovery durations (s): {'verify': 5.219199}  ·  **MTTR: 5.219199 s** (MTTR = total recovery duration across recovered failure events / number of recovered failure events; unrecovered failures are excluded from the denominator)
- Latency: end-to-end 5.416517 s = active 5.405873 s + human wait 0.010644 s

## Event timeline

| seq | at | actor | kind | stage | attempt | result | reason |
|---|---|---|---|---|---|---|---|
| 1 | 2026-10-18T18:02:34.830683+00:00 | system | run_created |  |  | CREATED | scope=greenfield planner=sdlc |
| 2 | 2026-10-18T18:02:34.835786+00:00 | system | run_started |  |  | RUNNING |  |
| 3 | 2026-10-18T18:02:34.838166+00:00 | system | stage_ready | ingest |  | READY |  |
| 4 | 2026-10-18T18:02:34.841994+00:00 | agent | stage_started | ingest | 1 | RUNNING |  |
| 5 | 2026-10-18T18:02:34.850380+00:00 | agent | stage_succeeded | ingest | 1 | SUCCEEDED |  |
| 6 | 2026-10-18T18:02:34.853300+00:00 | system | stage_ready | quality_check |  | READY |  |
| 7 | 2026-10-18T18:02:34.856288+00:00 | agent | stage_started | quality_check | 1 | RUNNING |  |
| 8 | 2026-10-18T18:02:34.861238+00:00 | agent | stage_succeeded | quality_check | 1 | SUCCEEDED |  |
| 9 | 2026-10-18T18:02:34.863638+00:00 | system | stage_skipped | clarification |  | SKIPPED | condition 'quality_check.clarification_required' is false |
| 10 | 2026-10-18T18:02:34.865436+00:00 | system | stage_ready | decompose |  | READY |  |
| 11 | 2026-10-18T18:02:34.867845+00:00 | agent | stage_started | decompose | 1 | RUNNING |  |
| 12 | 2026-10-18T18:02:34.874700+00:00 | agent | stage_succeeded | decompose | 1 | SUCCEEDED |  |
| 13 | 2026-10-18T18:02:34.877650+00:00 | system | stage_ready | design |  | READY |  |
| 14 | 2026-10-18T18:02:34.880505+00:00 | agent | stage_started | design | 1 | RUNNING |  |
| 15 | 2026-10-18T18:02:34.888277+00:00 | agent | stage_succeeded | design | 1 | SUCCEEDED |  |
| 16 | 2026-10-18T18:02:34.893149+00:00 | system | gate_opened | design_approval |  | WAITING | architecture approval; API/schema changes must be acknowledged (CHG-002) |
| 17 | 2026-10-18T18:02:34.899220+00:00 | human | decision_recorded | design_approval |  | approve | design stays inside existing module boundaries; API/schema change acknowledged |
| 18 | 2026-10-18T18:02:34.908170+00:00 | system | stage_ready | docs_draft |  | READY |  |
| 19 | 2026-10-18T18:02:34.910739+00:00 | system | stage_ready | implement |  | READY |  |
| 20 | 2026-10-18T18:02:34.912602+00:00 | system | stage_ready | test_plan |  | READY |  |
| 21 | 2026-10-18T18:02:34.916035+00:00 | agent | stage_started | docs_draft | 1 | RUNNING |  |
| 22 | 2026-10-18T18:02:34.918804+00:00 | agent | stage_started | implement | 1 | RUNNING |  |
| 23 | 2026-10-18T18:02:34.922014+00:00 | agent | stage_started | test_plan | 1 | RUNNING |  |
| 24 | 2026-10-18T18:02:34.928199+00:00 | agent | stage_succeeded | docs_draft | 1 | SUCCEEDED |  |
| 25 | 2026-10-18T18:02:34.935294+00:00 | agent | stage_succeeded | implement | 1 | SUCCEEDED |  |
| 26 | 2026-10-18T18:02:34.941786+00:00 | agent | stage_succeeded | test_plan | 1 | SUCCEEDED |  |
| 27 | 2026-10-18T18:02:34.944923+00:00 | system | stage_ready | verify |  | READY |  |
| 28 | 2026-10-18T18:02:34.948529+00:00 | agent | stage_started | verify | 1 | RUNNING |  |
| 29 | 2026-10-18T18:02:34.951694+00:00 | system | failure_detected | verify | 1 | TRANSIENT | injected transient fault (demo) on attempt 1 of 2 |
| 30 | 2026-10-18T18:02:34.955303+00:00 | system | retry_scheduled | verify | 1 | RETRYING | injected transient fault (demo) on attempt 1 of 2 |
| 31 | 2026-10-18T18:02:34.956397+00:00 | system | recovery_started | verify | 1 |  |  |
| 32 | 2026-10-18T18:02:35.060112+00:00 | agent | stage_started | verify | 2 | RUNNING |  |
| 33 | 2026-10-18T18:02:35.065478+00:00 | system | retry_scheduled | verify | 2 | RETRYING | injected transient fault (demo) on attempt 2 of 2 |
| 34 | 2026-10-18T18:02:35.066711+00:00 | system | recovery_started | verify | 2 |  |  |
| 35 | 2026-10-18T18:02:35.270753+00:00 | agent | stage_started | verify | 3 | RUNNING |  |
| 36 | 2026-10-18T18:02:40.168808+00:00 | agent | stage_succeeded | verify | 3 | SUCCEEDED |  |
| 37 | 2026-10-18T18:02:40.170893+00:00 | system | recovery_completed | verify | 3 | RECOVERED |  |
| 38 | 2026-10-18T18:02:40.173690+00:00 | system | stage_ready | security_review |  | READY |  |
| 39 | 2026-10-18T18:02:40.177153+00:00 | agent | stage_started | security_review | 1 | RUNNING |  |
| 40 | 2026-10-18T18:02:40.184765+00:00 | agent | stage_succeeded | security_review | 1 | SUCCEEDED |  |
| 41 | 2026-10-18T18:02:40.188182+00:00 | system | stage_ready | compliance_check |  | READY |  |
| 42 | 2026-10-18T18:02:40.191681+00:00 | agent | stage_started | compliance_check | 1 | RUNNING |  |
| 43 | 2026-10-18T18:02:40.213657+00:00 | agent | stage_succeeded | compliance_check | 1 | SUCCEEDED |  |
| 44 | 2026-10-18T18:02:40.216475+00:00 | system | stage_skipped | policy_exception |  | SKIPPED | condition 'compliance_check.blocking non-empty' is false |
| 45 | 2026-10-18T18:02:40.219326+00:00 | system | gate_opened | release_readiness |  | WAITING | human release-readiness decision on the computed evidence |
| 46 | 2026-10-18T18:02:40.223899+00:00 | human | decision_recorded | release_readiness |  | approve | verification executed, policies evaluated, evidence exported |
| 47 | 2026-10-18T18:02:40.233409+00:00 | system | stage_ready | summary |  | READY |  |
| 48 | 2026-10-18T18:02:40.236009+00:00 | agent | stage_started | summary | 1 | RUNNING |  |
| 49 | 2026-10-18T18:02:40.244990+00:00 | agent | stage_succeeded | summary | 1 | SUCCEEDED |  |
| 50 | 2026-10-18T18:02:40.247200+00:00 | system | run_completed |  |  | COMPLETED | all stages done |
