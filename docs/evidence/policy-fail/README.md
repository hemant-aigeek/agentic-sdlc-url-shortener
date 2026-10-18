# Run 01a1502f801e8c7a9ffe691f73 — Demo: forced mandatory policy failure (SEC-002) safe-stops the run

> Executed run export. Measurements are **demonstration data** from a local,
> single-process run with deterministic agents; not production statistics.

- Scope: `greenfield`  ·  State: `SAFE_STOPPED`  ·  Reason: POLICY_BLOCKED: mandatory policy failed with no admissible exception: SEC-002: injected demonstration fault (settings.demo_fault_policy_fail)
- Requirement version: 1  ·  Graph version: 1  ·  Policy version: 1.0.0
- Events: 37  ·  Decisions: 1  ·  Replans: 0

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
| compliance_check | agent | FAILED | 1 |  |  | verify, security_review |
| policy_exception | human | PENDING | 0 |  |  | compliance_check |
| release_readiness | human | PENDING | 0 |  |  | policy_exception |
| summary | agent | PENDING | 0 |  |  | release_readiness |

## Human decisions

| gate | actor | decision | reason | at |
|---|---|---|---|---|
| design_approval | hemant | approve | design stays inside existing module boundaries; API/schema change acknowledged | 2026-10-18 18:04:12.794752+00:00 |

## Policy evaluations

| policy | version | outcome | detail |
|---|---|---|---|
| SEC-001 | 1.0.0 | PASS | change set does not touch URL validation |
| SEC-002 | 1.0.0 | FAIL | injected demonstration fault (settings.demo_fault_policy_fail) |
| SEC-003 | 1.0.0 | PASS | automated security review completed |
| CMP-001 | 1.0.0 | PASS | 10 executed stages and 1 gates fully recorded |
| CMP-002 | 1.0.0 | PASS | 34 audit events carry actor, action, timestamp and target |
| CHG-001 | 1.0.0 | NOT-APPLICABLE | scope is greenfield; impact analysis is required for brownfield only |
| CHG-002 | 1.0.0 | PASS | API/schema change acknowledged at design approval |
| DEP-001 | 1.0.0 | PASS | no new dependencies declared |
| AUD-001 | 1.0.0 | PASS | audit retention recorded: life of the local store |

## Metrics (demonstration)

- Stage success rate: 0.9090909090909091  ·  failure rate: 0.09090909090909091
- Retries: 0 (timeouts 0)  ·  fallbacks: 0  ·  compensations: 0  ·  safe-stops: 1  ·  replans: 0
- Recovered failures: 0  ·  unrecovered: 1 ['compliance_check']
- Recovery durations (s): {}  ·  **MTTR: None s** (MTTR = total recovery duration across recovered failure events / number of recovered failure events; unrecovered failures are excluded from the denominator)
- Latency: end-to-end 5.246176 s = active 5.239698 s + human wait 0.006478 s

## Event timeline

| seq | at | actor | kind | stage | attempt | result | reason |
|---|---|---|---|---|---|---|---|
| 1 | 2026-10-18T18:04:12.724640+00:00 | system | run_created |  |  | CREATED | scope=greenfield planner=sdlc |
| 2 | 2026-10-18T18:04:12.731175+00:00 | system | run_started |  |  | RUNNING |  |
| 3 | 2026-10-18T18:04:12.733955+00:00 | system | stage_ready | ingest |  | READY |  |
| 4 | 2026-10-18T18:04:12.737312+00:00 | agent | stage_started | ingest | 1 | RUNNING |  |
| 5 | 2026-10-18T18:04:12.744410+00:00 | agent | stage_succeeded | ingest | 1 | SUCCEEDED |  |
| 6 | 2026-10-18T18:04:12.747947+00:00 | system | stage_ready | quality_check |  | READY |  |
| 7 | 2026-10-18T18:04:12.751185+00:00 | agent | stage_started | quality_check | 1 | RUNNING |  |
| 8 | 2026-10-18T18:04:12.757781+00:00 | agent | stage_succeeded | quality_check | 1 | SUCCEEDED |  |
| 9 | 2026-10-18T18:04:12.761167+00:00 | system | stage_skipped | clarification |  | SKIPPED | condition 'quality_check.clarification_required' is false |
| 10 | 2026-10-18T18:04:12.763622+00:00 | system | stage_ready | decompose |  | READY |  |
| 11 | 2026-10-18T18:04:12.766791+00:00 | agent | stage_started | decompose | 1 | RUNNING |  |
| 12 | 2026-10-18T18:04:12.773009+00:00 | agent | stage_succeeded | decompose | 1 | SUCCEEDED |  |
| 13 | 2026-10-18T18:04:12.776235+00:00 | system | stage_ready | design |  | READY |  |
| 14 | 2026-10-18T18:04:12.779471+00:00 | agent | stage_started | design | 1 | RUNNING |  |
| 15 | 2026-10-18T18:04:12.786413+00:00 | agent | stage_succeeded | design | 1 | SUCCEEDED |  |
| 16 | 2026-10-18T18:04:12.790254+00:00 | system | gate_opened | design_approval |  | WAITING | architecture approval; API/schema changes must be acknowledged (CHG-002) |
| 17 | 2026-10-18T18:04:12.796732+00:00 | human | decision_recorded | design_approval |  | approve | design stays inside existing module boundaries; API/schema change acknowledged |
| 18 | 2026-10-18T18:04:12.805708+00:00 | system | stage_ready | docs_draft |  | READY |  |
| 19 | 2026-10-18T18:04:12.808016+00:00 | system | stage_ready | implement |  | READY |  |
| 20 | 2026-10-18T18:04:12.809996+00:00 | system | stage_ready | test_plan |  | READY |  |
| 21 | 2026-10-18T18:04:12.812859+00:00 | agent | stage_started | docs_draft | 1 | RUNNING |  |
| 22 | 2026-10-18T18:04:12.815713+00:00 | agent | stage_started | implement | 1 | RUNNING |  |
| 23 | 2026-10-18T18:04:12.818273+00:00 | agent | stage_started | test_plan | 1 | RUNNING |  |
| 24 | 2026-10-18T18:04:12.824849+00:00 | agent | stage_succeeded | docs_draft | 1 | SUCCEEDED |  |
| 25 | 2026-10-18T18:04:12.830261+00:00 | agent | stage_succeeded | test_plan | 1 | SUCCEEDED |  |
| 26 | 2026-10-18T18:04:12.836288+00:00 | agent | stage_succeeded | implement | 1 | SUCCEEDED |  |
| 27 | 2026-10-18T18:04:12.839137+00:00 | system | stage_ready | verify |  | READY |  |
| 28 | 2026-10-18T18:04:12.841617+00:00 | agent | stage_started | verify | 1 | RUNNING |  |
| 29 | 2026-10-18T18:04:17.924371+00:00 | agent | stage_succeeded | verify | 1 | SUCCEEDED |  |
| 30 | 2026-10-18T18:04:17.927768+00:00 | system | stage_ready | security_review |  | READY |  |
| 31 | 2026-10-18T18:04:17.930731+00:00 | agent | stage_started | security_review | 1 | RUNNING |  |
| 32 | 2026-10-18T18:04:17.937286+00:00 | agent | stage_succeeded | security_review | 1 | SUCCEEDED |  |
| 33 | 2026-10-18T18:04:17.940213+00:00 | system | stage_ready | compliance_check |  | READY |  |
| 34 | 2026-10-18T18:04:17.942944+00:00 | agent | stage_started | compliance_check | 1 | RUNNING |  |
| 35 | 2026-10-18T18:04:17.964419+00:00 | system | failure_detected | compliance_check | 1 | PERMANENT | mandatory policy failed with no admissible exception: SEC-002: injected demonstration fault (settings.demo_fault_policy_fail) |
| 36 | 2026-10-18T18:04:17.967606+00:00 | agent | stage_failed | compliance_check | 1 | FAILED | mandatory policy failed with no admissible exception: SEC-002: injected demonstration fault (settings.demo_fault_policy_fail) |
| 37 | 2026-10-18T18:04:17.970816+00:00 | system | safe_stop |  |  | SAFE_STOPPED | POLICY_BLOCKED: mandatory policy failed with no admissible exception: SEC-002: injected demonstration fault (settings.demo_fault_policy_fail) |
