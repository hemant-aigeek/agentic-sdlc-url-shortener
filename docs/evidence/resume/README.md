# Run 01a1502e97430c8446291361be — Demo: interruption after one batch, resumed by a fresh engine

> Executed run export. Measurements are **demonstration data** from a local,
> single-process run with deterministic agents; not production statistics.

- Scope: `greenfield`  ·  State: `COMPLETED`
- Requirement version: 1  ·  Graph version: 1  ·  Policy version: 1.0.0
- Events: 44  ·  Decisions: 2  ·  Replans: 0

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
| verify | agent | SUCCEEDED | 1 |  |  | implement, test_plan, docs_draft |
| security_review | agent | SUCCEEDED | 1 |  |  | verify |
| compliance_check | agent | SUCCEEDED | 1 |  |  | verify, security_review |
| policy_exception | human | SKIPPED | 0 |  |  | compliance_check |
| release_readiness | human | SUCCEEDED | 0 |  |  | policy_exception |
| summary | agent | SUCCEEDED | 1 |  |  | release_readiness |

## Human decisions

| gate | actor | decision | reason | at |
|---|---|---|---|---|
| design_approval | hemant | approve | design stays inside existing module boundaries; API/schema change acknowledged | 2026-10-18 18:03:13.199310+00:00 |
| release_readiness | hemant | approve | verification executed, policies evaluated, evidence exported | 2026-10-18 18:03:18.540519+00:00 |

## Policy evaluations

| policy | version | outcome | detail |
|---|---|---|---|
| SEC-001 | 1.0.0 | PASS | change set does not touch URL validation |
| SEC-002 | 1.0.0 | PASS | no secret patterns in 9 artifacts |
| SEC-003 | 1.0.0 | PASS | automated security review completed |
| CMP-001 | 1.0.0 | PASS | 10 executed stages and 1 gates fully recorded |
| CMP-002 | 1.0.0 | PASS | 36 audit events carry actor, action, timestamp and target |
| CHG-001 | 1.0.0 | NOT-APPLICABLE | scope is greenfield; impact analysis is required for brownfield only |
| CHG-002 | 1.0.0 | PASS | API/schema change acknowledged at design approval |
| DEP-001 | 1.0.0 | PASS | no new dependencies declared |
| AUD-001 | 1.0.0 | PASS | audit retention recorded: life of the local store |

## Metrics (demonstration)

- Stage success rate: 1.0  ·  failure rate: 0.0
- Retries: 0 (timeouts 0)  ·  fallbacks: 0  ·  compensations: 0  ·  safe-stops: 0  ·  replans: 0
- Recovered failures: 0  ·  unrecovered: 0 []
- Recovery durations (s): {}  ·  **MTTR: None s** (MTTR = total recovery duration across recovered failure events / number of recovered failure events; unrecovered failures are excluded from the denominator)
- Latency: end-to-end 5.454692 s = active 5.441014999999999 s + human wait 0.013677000000000002 s

## Event timeline

| seq | at | actor | kind | stage | attempt | result | reason |
|---|---|---|---|---|---|---|---|
| 1 | 2026-10-18T18:03:13.113981+00:00 | system | run_created |  |  | CREATED | scope=greenfield planner=sdlc |
| 2 | 2026-10-18T18:03:13.120809+00:00 | system | run_started |  |  | RUNNING |  |
| 3 | 2026-10-18T18:03:13.123443+00:00 | system | stage_ready | ingest |  | READY |  |
| 4 | 2026-10-18T18:03:13.126474+00:00 | agent | stage_started | ingest | 1 | RUNNING |  |
| 5 | 2026-10-18T18:03:13.134615+00:00 | agent | stage_succeeded | ingest | 1 | SUCCEEDED |  |
| 6 | 2026-10-18T18:03:13.137968+00:00 | system | run_suspended |  |  | SUSPENDED | max_batches reached |
| 7 | 2026-10-18T18:03:13.140336+00:00 | system | run_resumed |  |  | SUSPENDED | resume requested |
| 8 | 2026-10-18T18:03:13.144819+00:00 | system | stage_ready | quality_check |  | READY |  |
| 9 | 2026-10-18T18:03:13.147698+00:00 | agent | stage_started | quality_check | 1 | RUNNING |  |
| 10 | 2026-10-18T18:03:13.153922+00:00 | agent | stage_succeeded | quality_check | 1 | SUCCEEDED |  |
| 11 | 2026-10-18T18:03:13.156614+00:00 | system | stage_skipped | clarification |  | SKIPPED | condition 'quality_check.clarification_required' is false |
| 12 | 2026-10-18T18:03:13.159450+00:00 | system | stage_ready | decompose |  | READY |  |
| 13 | 2026-10-18T18:03:13.162505+00:00 | agent | stage_started | decompose | 1 | RUNNING |  |
| 14 | 2026-10-18T18:03:13.168527+00:00 | agent | stage_succeeded | decompose | 1 | SUCCEEDED |  |
| 15 | 2026-10-18T18:03:13.173547+00:00 | system | stage_ready | design |  | READY |  |
| 16 | 2026-10-18T18:03:13.177949+00:00 | agent | stage_started | design | 1 | RUNNING |  |
| 17 | 2026-10-18T18:03:13.188822+00:00 | agent | stage_succeeded | design | 1 | SUCCEEDED |  |
| 18 | 2026-10-18T18:03:13.193531+00:00 | system | gate_opened | design_approval |  | WAITING | architecture approval; API/schema changes must be acknowledged (CHG-002) |
| 19 | 2026-10-18T18:03:13.202123+00:00 | human | decision_recorded | design_approval |  | approve | design stays inside existing module boundaries; API/schema change acknowledged |
| 20 | 2026-10-18T18:03:13.214110+00:00 | system | stage_ready | docs_draft |  | READY |  |
| 21 | 2026-10-18T18:03:13.216616+00:00 | system | stage_ready | implement |  | READY |  |
| 22 | 2026-10-18T18:03:13.219197+00:00 | system | stage_ready | test_plan |  | READY |  |
| 23 | 2026-10-18T18:03:13.223340+00:00 | agent | stage_started | docs_draft | 1 | RUNNING |  |
| 24 | 2026-10-18T18:03:13.226145+00:00 | agent | stage_started | implement | 1 | RUNNING |  |
| 25 | 2026-10-18T18:03:13.229776+00:00 | agent | stage_started | test_plan | 1 | RUNNING |  |
| 26 | 2026-10-18T18:03:13.237284+00:00 | agent | stage_succeeded | docs_draft | 1 | SUCCEEDED |  |
| 27 | 2026-10-18T18:03:13.243951+00:00 | agent | stage_succeeded | test_plan | 1 | SUCCEEDED |  |
| 28 | 2026-10-18T18:03:13.249675+00:00 | agent | stage_succeeded | implement | 1 | SUCCEEDED |  |
| 29 | 2026-10-18T18:03:13.252817+00:00 | system | stage_ready | verify |  | READY |  |
| 30 | 2026-10-18T18:03:13.256516+00:00 | agent | stage_started | verify | 1 | RUNNING |  |
| 31 | 2026-10-18T18:03:18.496252+00:00 | agent | stage_succeeded | verify | 1 | SUCCEEDED |  |
| 32 | 2026-10-18T18:03:18.498885+00:00 | system | stage_ready | security_review |  | READY |  |
| 33 | 2026-10-18T18:03:18.501258+00:00 | agent | stage_started | security_review | 1 | RUNNING |  |
| 34 | 2026-10-18T18:03:18.506930+00:00 | agent | stage_succeeded | security_review | 1 | SUCCEEDED |  |
| 35 | 2026-10-18T18:03:18.509807+00:00 | system | stage_ready | compliance_check |  | READY |  |
| 36 | 2026-10-18T18:03:18.512680+00:00 | agent | stage_started | compliance_check | 1 | RUNNING |  |
| 37 | 2026-10-18T18:03:18.530853+00:00 | agent | stage_succeeded | compliance_check | 1 | SUCCEEDED |  |
| 38 | 2026-10-18T18:03:18.533686+00:00 | system | stage_skipped | policy_exception |  | SKIPPED | condition 'compliance_check.blocking non-empty' is false |
| 39 | 2026-10-18T18:03:18.536600+00:00 | system | gate_opened | release_readiness |  | WAITING | human release-readiness decision on the computed evidence |
| 40 | 2026-10-18T18:03:18.541685+00:00 | human | decision_recorded | release_readiness |  | approve | verification executed, policies evaluated, evidence exported |
| 41 | 2026-10-18T18:03:18.550836+00:00 | system | stage_ready | summary |  | READY |  |
| 42 | 2026-10-18T18:03:18.553258+00:00 | agent | stage_started | summary | 1 | RUNNING |  |
| 43 | 2026-10-18T18:03:18.563600+00:00 | agent | stage_succeeded | summary | 1 | SUCCEEDED |  |
| 44 | 2026-10-18T18:03:18.568673+00:00 | system | run_completed |  |  | COMPLETED | all stages done |
