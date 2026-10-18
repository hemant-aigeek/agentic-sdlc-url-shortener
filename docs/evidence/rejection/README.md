# Run 01a1502e7e828b519da9c898ae — Demo: release rejected -> change set rolled back

> Executed run export. Measurements are **demonstration data** from a local,
> single-process run with deterministic agents; not production statistics.

- Scope: `greenfield`  ·  State: `REJECTED`  ·  Reason: REJECTED at release_readiness: not this sprint; defer the endpoint
- Requirement version: 1  ·  Graph version: 1  ·  Policy version: 1.0.0
- Events: 41  ·  Decisions: 2  ·  Replans: 0

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
| implement | agent | COMPENSATED | 1 | after:design_approval |  | design_approval |
| test_plan | agent | SUCCEEDED | 1 | after:design_approval |  | design_approval |
| verify | agent | SUCCEEDED | 1 |  |  | implement, test_plan, docs_draft |
| security_review | agent | SUCCEEDED | 1 |  |  | verify |
| compliance_check | agent | SUCCEEDED | 1 |  |  | verify, security_review |
| policy_exception | human | SKIPPED | 0 |  |  | compliance_check |
| release_readiness | human | FAILED | 0 |  |  | policy_exception |
| summary | agent | PENDING | 0 |  |  | release_readiness |

## Human decisions

| gate | actor | decision | reason | at |
|---|---|---|---|---|
| design_approval | hemant | approve | design stays inside existing module boundaries; API/schema change acknowledged | 2026-10-18 18:03:06.852442+00:00 |
| release_readiness | hemant | reject | not this sprint; defer the endpoint | 2026-10-18 18:03:12.239228+00:00 |

## Policy evaluations

| policy | version | outcome | detail |
|---|---|---|---|
| SEC-001 | 1.0.0 | PASS | change set does not touch URL validation |
| SEC-002 | 1.0.0 | PASS | no secret patterns in 9 artifacts |
| SEC-003 | 1.0.0 | PASS | automated security review completed |
| CMP-001 | 1.0.0 | PASS | 10 executed stages and 1 gates fully recorded |
| CMP-002 | 1.0.0 | PASS | 34 audit events carry actor, action, timestamp and target |
| CHG-001 | 1.0.0 | NOT-APPLICABLE | scope is greenfield; impact analysis is required for brownfield only |
| CHG-002 | 1.0.0 | PASS | API/schema change acknowledged at design approval |
| DEP-001 | 1.0.0 | PASS | no new dependencies declared |
| AUD-001 | 1.0.0 | PASS | audit retention recorded: life of the local store |

## Metrics (demonstration)

- Stage success rate: 0.9090909090909091  ·  failure rate: 0.09090909090909091
- Retries: 0 (timeouts 0)  ·  fallbacks: 0  ·  compensations: 1  ·  safe-stops: 0  ·  replans: 0
- Recovered failures: 0  ·  unrecovered: 0 []
- Recovery durations (s): {}  ·  **MTTR: None s** (MTTR = total recovery duration across recovered failure events / number of recovered failure events; unrecovered failures are excluded from the denominator)
- Latency: end-to-end 5.46878 s = active 5.456606 s + human wait 0.012174 s

## Event timeline

| seq | at | actor | kind | stage | attempt | result | reason |
|---|---|---|---|---|---|---|---|
| 1 | 2026-10-18T18:03:06.782369+00:00 | system | run_created |  |  | CREATED | scope=greenfield planner=sdlc |
| 2 | 2026-10-18T18:03:06.789743+00:00 | system | run_started |  |  | RUNNING |  |
| 3 | 2026-10-18T18:03:06.792940+00:00 | system | stage_ready | ingest |  | READY |  |
| 4 | 2026-10-18T18:03:06.796278+00:00 | agent | stage_started | ingest | 1 | RUNNING |  |
| 5 | 2026-10-18T18:03:06.802802+00:00 | agent | stage_succeeded | ingest | 1 | SUCCEEDED |  |
| 6 | 2026-10-18T18:03:06.805700+00:00 | system | stage_ready | quality_check |  | READY |  |
| 7 | 2026-10-18T18:03:06.808201+00:00 | agent | stage_started | quality_check | 1 | RUNNING |  |
| 8 | 2026-10-18T18:03:06.813700+00:00 | agent | stage_succeeded | quality_check | 1 | SUCCEEDED |  |
| 9 | 2026-10-18T18:03:06.816270+00:00 | system | stage_skipped | clarification |  | SKIPPED | condition 'quality_check.clarification_required' is false |
| 10 | 2026-10-18T18:03:06.818370+00:00 | system | stage_ready | decompose |  | READY |  |
| 11 | 2026-10-18T18:03:06.821518+00:00 | agent | stage_started | decompose | 1 | RUNNING |  |
| 12 | 2026-10-18T18:03:06.827900+00:00 | agent | stage_succeeded | decompose | 1 | SUCCEEDED |  |
| 13 | 2026-10-18T18:03:06.831146+00:00 | system | stage_ready | design |  | READY |  |
| 14 | 2026-10-18T18:03:06.834811+00:00 | agent | stage_started | design | 1 | RUNNING |  |
| 15 | 2026-10-18T18:03:06.843008+00:00 | agent | stage_succeeded | design | 1 | SUCCEEDED |  |
| 16 | 2026-10-18T18:03:06.847641+00:00 | system | gate_opened | design_approval |  | WAITING | architecture approval; API/schema changes must be acknowledged (CHG-002) |
| 17 | 2026-10-18T18:03:06.854732+00:00 | human | decision_recorded | design_approval |  | approve | design stays inside existing module boundaries; API/schema change acknowledged |
| 18 | 2026-10-18T18:03:06.864381+00:00 | system | stage_ready | docs_draft |  | READY |  |
| 19 | 2026-10-18T18:03:06.866770+00:00 | system | stage_ready | implement |  | READY |  |
| 20 | 2026-10-18T18:03:06.872866+00:00 | system | stage_ready | test_plan |  | READY |  |
| 21 | 2026-10-18T18:03:06.877294+00:00 | agent | stage_started | docs_draft | 1 | RUNNING |  |
| 22 | 2026-10-18T18:03:06.880302+00:00 | agent | stage_started | implement | 1 | RUNNING |  |
| 23 | 2026-10-18T18:03:06.883365+00:00 | agent | stage_started | test_plan | 1 | RUNNING |  |
| 24 | 2026-10-18T18:03:06.890560+00:00 | agent | stage_succeeded | docs_draft | 1 | SUCCEEDED |  |
| 25 | 2026-10-18T18:03:06.902475+00:00 | agent | stage_succeeded | implement | 1 | SUCCEEDED |  |
| 26 | 2026-10-18T18:03:06.922759+00:00 | agent | stage_succeeded | test_plan | 1 | SUCCEEDED |  |
| 27 | 2026-10-18T18:03:06.929639+00:00 | system | stage_ready | verify |  | READY |  |
| 28 | 2026-10-18T18:03:06.932796+00:00 | agent | stage_started | verify | 1 | RUNNING |  |
| 29 | 2026-10-18T18:03:12.191366+00:00 | agent | stage_succeeded | verify | 1 | SUCCEEDED |  |
| 30 | 2026-10-18T18:03:12.194983+00:00 | system | stage_ready | security_review |  | READY |  |
| 31 | 2026-10-18T18:03:12.197495+00:00 | agent | stage_started | security_review | 1 | RUNNING |  |
| 32 | 2026-10-18T18:03:12.204608+00:00 | agent | stage_succeeded | security_review | 1 | SUCCEEDED |  |
| 33 | 2026-10-18T18:03:12.207156+00:00 | system | stage_ready | compliance_check |  | READY |  |
| 34 | 2026-10-18T18:03:12.210060+00:00 | agent | stage_started | compliance_check | 1 | RUNNING |  |
| 35 | 2026-10-18T18:03:12.229498+00:00 | agent | stage_succeeded | compliance_check | 1 | SUCCEEDED |  |
| 36 | 2026-10-18T18:03:12.232138+00:00 | system | stage_skipped | policy_exception |  | SKIPPED | condition 'compliance_check.blocking non-empty' is false |
| 37 | 2026-10-18T18:03:12.235273+00:00 | system | gate_opened | release_readiness |  | WAITING | human release-readiness decision on the computed evidence |
| 38 | 2026-10-18T18:03:12.240356+00:00 | human | decision_recorded | release_readiness |  | reject | not this sprint; defer the endpoint |
| 39 | 2026-10-18T18:03:12.245566+00:00 | system | compensation_started | implement |  |  | rejected at release_readiness |
| 40 | 2026-10-18T18:03:12.248824+00:00 | agent | rollback_completed | implement |  | COMPENSATED | rejected at release_readiness |
| 41 | 2026-10-18T18:03:12.251149+00:00 | system | run_rejected |  |  | REJECTED | rejected at release_readiness: not this sprint; defer the endpoint |
