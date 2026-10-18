# Run 01a1502f681045c398f321de78 — SCN-C ambiguous: links expire 'after a while' and are 'reusable'

> Executed run export. Measurements are **demonstration data** from a local,
> single-process run with deterministic agents; not production statistics.

- Scope: `auto`  ·  State: `COMPLETED`
- Requirement version: 2  ·  Graph version: 2  ·  Policy version: 1.0.0
- Events: 54  ·  Decisions: 4  ·  Replans: 1

## Stages

| stage | owner | state | attempt | parallel group | fallback | depends on |
|---|---|---|---|---|---|---|
| ingest | agent | SUCCEEDED | 1 |  |  |  |
| quality_check | agent | SUCCEEDED | 1 |  |  | ingest |
| clarification | human | SUCCEEDED | 0 |  |  | quality_check |
| requirement_revision | agent | SUCCEEDED | 1 |  |  | clarification |
| impact_analysis | agent | SKIPPED | 0 |  |  | requirement_revision |
| decompose | agent | SUCCEEDED | 1 |  |  | impact_analysis |
| design | agent | SUCCEEDED | 1 |  |  | decompose |
| design_approval | human | SUCCEEDED | 0 |  |  | design |
| docs_draft | agent | SUCCEEDED | 1 | after:design_approval |  | design_approval |
| implement | agent | SUCCEEDED | 1 | after:design_approval |  | design_approval |
| test_plan | agent | SUCCEEDED | 1 | after:design_approval |  | design_approval |
| verify | agent | SUCCEEDED | 1 |  |  | implement, test_plan, docs_draft |
| security_review | agent | FALLBACK | 1 |  | yes | verify |
| compliance_check | agent | SUCCEEDED | 1 |  |  | verify, security_review |
| policy_exception | human | SUCCEEDED | 0 |  |  | compliance_check |
| release_readiness | human | SUCCEEDED | 0 |  |  | policy_exception |
| summary | agent | SUCCEEDED | 1 |  |  | release_readiness |

## Human decisions

| gate | actor | decision | reason | at |
|---|---|---|---|---|
| clarification | hemant | clarify | expire 30 days after creation; short codes are never reused (FR-U04 stands) | 2026-10-18 18:04:06.608439+00:00 |
| design_approval | hemant | approve | design stays inside existing module boundaries; API/schema change acknowledged | 2026-10-18 18:04:06.676555+00:00 |
| policy_exception | hemant | approve | manual security checklist completed; residual risk accepted for this run | 2026-10-18 18:04:11.937946+00:00 |
| release_readiness | hemant | approve | verification executed, policies evaluated, evidence exported | 2026-10-18 18:04:11.953856+00:00 |

## Policy evaluations

| policy | version | outcome | detail |
|---|---|---|---|
| SEC-001 | 1.0.0 | PASS | change set does not touch URL validation |
| SEC-002 | 1.0.0 | PASS | no secret patterns in 10 artifacts |
| SEC-003 | 1.0.0 | EXCEPTION-REQUESTED | automated security review fell back to manual review; a human must accept the residual risk with a compensating control |
| CMP-001 | 1.0.0 | PASS | 11 executed stages and 2 gates fully recorded |
| CMP-002 | 1.0.0 | PASS | 44 audit events carry actor, action, timestamp and target |
| CHG-001 | 1.0.0 | NOT-APPLICABLE | scope is greenfield; impact analysis is required for brownfield only |
| CHG-002 | 1.0.0 | PASS | API/schema change acknowledged at design approval |
| DEP-001 | 1.0.0 | PASS | no new dependencies declared |
| AUD-001 | 1.0.0 | PASS | audit retention recorded: life of the local store |

### Policy exceptions

| policy | status | approver | compensating control | expires |
|---|---|---|---|---|
| SEC-003 | approved | hemant | manual security checklist reviewed and attached | 2026-11-17 18:04:11.937946+00:00 |

## Replanning events

- 2026-10-18 18:04:06.627092+00:00: clarification at clarification — invalidated ['compliance_check', 'decompose', 'design', 'design_approval', 'docs_draft', 'impact_analysis', 'implement', 'policy_exception', 'release_readiness', 'requirement_revision', 'security_review', 'summary', 'test_plan', 'verify']

## Metrics (demonstration)

- Stage success rate: 0.9375  ·  failure rate: 0.0
- Retries: 0 (timeouts 0)  ·  fallbacks: 1  ·  compensations: 0  ·  safe-stops: 0  ·  replans: 1
- Recovered failures: 1  ·  unrecovered: 0 []
- Recovery durations (s): {'security_review': 0.009677}  ·  **MTTR: 0.009677 s** (MTTR = total recovery duration across recovered failure events / number of recovered failure events; unrecovered failures are excluded from the denominator)
- Latency: end-to-end 5.41006 s = active 5.387537999999999 s + human wait 0.022522 s

## Event timeline

| seq | at | actor | kind | stage | attempt | result | reason |
|---|---|---|---|---|---|---|---|
| 1 | 2026-10-18T18:04:06.567818+00:00 | system | run_created |  |  | CREATED | scope=auto planner=sdlc |
| 2 | 2026-10-18T18:04:06.573797+00:00 | system | run_started |  |  | RUNNING |  |
| 3 | 2026-10-18T18:04:06.577771+00:00 | system | stage_ready | ingest |  | READY |  |
| 4 | 2026-10-18T18:04:06.580509+00:00 | agent | stage_started | ingest | 1 | RUNNING |  |
| 5 | 2026-10-18T18:04:06.587832+00:00 | agent | stage_succeeded | ingest | 1 | SUCCEEDED |  |
| 6 | 2026-10-18T18:04:06.591538+00:00 | system | stage_ready | quality_check |  | READY |  |
| 7 | 2026-10-18T18:04:06.595629+00:00 | agent | stage_started | quality_check | 1 | RUNNING |  |
| 8 | 2026-10-18T18:04:06.600897+00:00 | agent | stage_succeeded | quality_check | 1 | SUCCEEDED |  |
| 9 | 2026-10-18T18:04:06.604228+00:00 | system | gate_opened | clarification |  | WAITING | human resolves material ambiguity before any design or implementation |
| 10 | 2026-10-18T18:04:06.610952+00:00 | human | decision_recorded | clarification |  | clarify | expire 30 days after creation; short codes are never reused (FR-U04 stands) |
| 11 | 2026-10-18T18:04:06.629191+00:00 | system | replan |  |  | v2 | clarification at clarification |
| 12 | 2026-10-18T18:04:06.634899+00:00 | system | stage_ready | requirement_revision |  | READY |  |
| 13 | 2026-10-18T18:04:06.637329+00:00 | agent | stage_started | requirement_revision | 1 | RUNNING |  |
| 14 | 2026-10-18T18:04:06.643433+00:00 | agent | stage_succeeded | requirement_revision | 1 | SUCCEEDED |  |
| 15 | 2026-10-18T18:04:06.645945+00:00 | system | stage_skipped | impact_analysis |  | SKIPPED | condition 'scope == brownfield' is false |
| 16 | 2026-10-18T18:04:06.647910+00:00 | system | stage_ready | decompose |  | READY |  |
| 17 | 2026-10-18T18:04:06.650734+00:00 | agent | stage_started | decompose | 1 | RUNNING |  |
| 18 | 2026-10-18T18:04:06.657449+00:00 | agent | stage_succeeded | decompose | 1 | SUCCEEDED |  |
| 19 | 2026-10-18T18:04:06.660874+00:00 | system | stage_ready | design |  | READY |  |
| 20 | 2026-10-18T18:04:06.664096+00:00 | agent | stage_started | design | 1 | RUNNING |  |
| 21 | 2026-10-18T18:04:06.669763+00:00 | agent | stage_succeeded | design | 1 | SUCCEEDED |  |
| 22 | 2026-10-18T18:04:06.673004+00:00 | system | gate_opened | design_approval |  | WAITING | architecture approval; API/schema changes must be acknowledged (CHG-002) |
| 23 | 2026-10-18T18:04:06.677708+00:00 | human | decision_recorded | design_approval |  | approve | design stays inside existing module boundaries; API/schema change acknowledged |
| 24 | 2026-10-18T18:04:06.685014+00:00 | system | stage_ready | docs_draft |  | READY |  |
| 25 | 2026-10-18T18:04:06.687021+00:00 | system | stage_ready | implement |  | READY |  |
| 26 | 2026-10-18T18:04:06.688972+00:00 | system | stage_ready | test_plan |  | READY |  |
| 27 | 2026-10-18T18:04:06.692709+00:00 | agent | stage_started | docs_draft | 1 | RUNNING |  |
| 28 | 2026-10-18T18:04:06.695232+00:00 | agent | stage_started | implement | 1 | RUNNING |  |
| 29 | 2026-10-18T18:04:06.698065+00:00 | agent | stage_started | test_plan | 1 | RUNNING |  |
| 30 | 2026-10-18T18:04:06.703871+00:00 | agent | stage_succeeded | docs_draft | 1 | SUCCEEDED |  |
| 31 | 2026-10-18T18:04:06.709145+00:00 | agent | stage_succeeded | test_plan | 1 | SUCCEEDED |  |
| 32 | 2026-10-18T18:04:06.715058+00:00 | agent | stage_succeeded | implement | 1 | SUCCEEDED |  |
| 33 | 2026-10-18T18:04:06.717972+00:00 | system | stage_ready | verify |  | READY |  |
| 34 | 2026-10-18T18:04:06.720411+00:00 | agent | stage_started | verify | 1 | RUNNING |  |
| 35 | 2026-10-18T18:04:11.888929+00:00 | agent | stage_succeeded | verify | 1 | SUCCEEDED |  |
| 36 | 2026-10-18T18:04:11.891729+00:00 | system | stage_ready | security_review |  | READY |  |
| 37 | 2026-10-18T18:04:11.894341+00:00 | agent | stage_started | security_review | 1 | RUNNING |  |
| 38 | 2026-10-18T18:04:11.896772+00:00 | system | failure_detected | security_review | 1 | PERMANENT | injected permanent fault (demo): automated security scanner unavailable |
| 39 | 2026-10-18T18:04:11.899643+00:00 | agent | stage_failed | security_review | 1 | FAILED | injected permanent fault (demo): automated security scanner unavailable |
| 40 | 2026-10-18T18:04:11.900648+00:00 | system | recovery_started | security_review | 1 |  |  |
| 41 | 2026-10-18T18:04:11.905445+00:00 | agent | fallback_used | security_review | 1 | FALLBACK | primary failed: injected permanent fault (demo): automated security scanner unavailable |
| 42 | 2026-10-18T18:04:11.906449+00:00 | system | recovery_completed | security_review | 1 | RECOVERED |  |
| 43 | 2026-10-18T18:04:11.908755+00:00 | system | stage_ready | compliance_check |  | READY |  |
| 44 | 2026-10-18T18:04:11.911501+00:00 | agent | stage_started | compliance_check | 1 | RUNNING |  |
| 45 | 2026-10-18T18:04:11.929219+00:00 | agent | stage_succeeded | compliance_check | 1 | SUCCEEDED |  |
| 46 | 2026-10-18T18:04:11.932722+00:00 | system | gate_opened | policy_exception |  | WAITING | human accepts a scoped, expiring policy exception + compensating control |
| 47 | 2026-10-18T18:04:11.939194+00:00 | human | decision_recorded | policy_exception |  | approve | manual security checklist completed; residual risk accepted for this run |
| 48 | 2026-10-18T18:04:11.944292+00:00 | human | exception_approved | policy_exception |  | approved | manual security checklist completed; residual risk accepted for this run |
| 49 | 2026-10-18T18:04:11.950222+00:00 | system | gate_opened | release_readiness |  | WAITING | human release-readiness decision on the computed evidence |
| 50 | 2026-10-18T18:04:11.954844+00:00 | human | decision_recorded | release_readiness |  | approve | verification executed, policies evaluated, evidence exported |
| 51 | 2026-10-18T18:04:11.962651+00:00 | system | stage_ready | summary |  | READY |  |
| 52 | 2026-10-18T18:04:11.965472+00:00 | agent | stage_started | summary | 1 | RUNNING |  |
| 53 | 2026-10-18T18:04:11.975513+00:00 | agent | stage_succeeded | summary | 1 | SUCCEEDED |  |
| 54 | 2026-10-18T18:04:11.977878+00:00 | system | run_completed |  |  | COMPLETED | all stages done |
