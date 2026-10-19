# Final Engineering Summary

**Project**: Agentic Software Engineering System — URL Shortener
**Repository**: https://github.com/hemant-aigeek/agentic-sdlc-url-shortener
**Author / decision owner**: Hemant Gupta
**Date**: 2026-10-19 · **Tag**: `assessment-submission-v1.0`

Every material claim below cites a repository path and, where applicable, a
command and the observable result. Vocabulary: *confirmed requirement* (from
the assignment), *approved assumption* (AS-xx, Gate 3), *demonstration
measurement* (local single-process run, injected faults), *production
recommendation* (documented, not built), *deferred scope* (`BACKLOG.md`),
*accepted limitation*, *unresolved blocker*.

---

## 1. Executive engineering outcome and release-readiness status

A working, locally runnable prototype of a governed, stateful, non-linear
agentic SDLC orchestrator, demonstrated on a production-disciplined URL
shortener. The repository-level release check
(`python scripts/release_check.py` → `docs/evidence/release-check.json`) is
**READY**: quality gate PASS (290 tests), dependency audit PASS (no known
vulnerabilities), licences allow-listed, six scenario exports present with
their expected terminal states.

The independent assessment (`docs/reviews/final-assessment.md`) and the
candidate's release decision are recorded in
`docs/approvals/GATE-5-release-readiness.md`. Decision: **READY WITH ACCEPTED
LIMITATIONS** — the limitations are listed in §19 and none is a mandatory
assignment gap; each is a conscious, recorded choice.

## 2. Project objective, scope, and 2–3-day timebox outcome

- **Objective** (assignment §1): transform a requirement into a reviewable
  engineering outcome with an agentic execution model, demonstrating
  requirement understanding, decomposition, multi-step execution and
  validation under controlled autonomy.
- **Scope decision** (plan §12, task TB-01): must-have = the orchestration
  control plane, governance, reliability, observability, three scenarios and
  evidence; the shortener kept deliberately small (create, redirect, expire,
  analytics, idempotency, health, auth, rate limit).
- **Timebox outcome**: all nine delivery slices (plan §12) completed. Day 1:
  governance artifacts + walking skeleton; Day 2: shortener + orchestration
  core + governance + reliability; Day 3: observability, agents, scenarios,
  security/release checks, documentation, review, release decision. Stop
  condition TB-04 (drop SCN-C fault injection) was not triggered. Deferred
  items are in `BACKLOG.md` with the reason and the cost to add each.

## 3. Confirmed requirements, assumptions, exclusions, and deferred scope

- **Confirmed requirements**: `specs/001-agentic-url-shortener/spec.md` —
  13 application-plane (FR-U), 20 orchestration (FR-O), 10 governance (FR-G),
  12 non-functional (NFR), 3 scenarios (SCN-A/B/C), 7 success criteria (SC).
  Every testable id has at least one test (`docs/traceability.md`,
  0 orphans; enforced by `tests/architecture/test_traceability.py`).
- **Approved assumptions** (Gate 3, `docs/approvals/GATE-3-clarifications.md`):
  AS-01 retry defaults (3 attempts, exponential backoff from 100 ms, 5 s
  per-attempt timeout); AS-02 performance figures are demonstration
  measurements; AS-03 suite < 2 min; AS-04 single process is sufficient;
  AS-05 reviewer has a Python runtime.
- **Clarifications** AMB-01…12 decided and recorded with rationale (same file);
  the material ones: new code per create (AMB-01), 7-char base62 (AMB-02),
  literal SSRF checks (AMB-03), best-effort analytics (AMB-05), static API key
  + actor header (AMB-06), deterministic agents (AMB-08), gate timeout →
  safe-stop (AMB-09), rollback only where reversible (AMB-10).
- **Exclusions** (spec §11): accounts/multi-tenancy/vanity codes, distributed
  workers/brokers, LLM-backed agents, production deployment, UI.
- **Deferred scope**: `BACKLOG.md` (LLM adapter, DNS-resolving SSRF check,
  dedupe index, Postgres, analytics outbox, OTel export, Docker Compose,
  gateway rate limiting, vanity codes).

## 4. Architecture overview and accepted ADRs

`docs/architecture.md`. One process, two planes with a tested import
direction (`tests/architecture/test_import_rules.py`): application plane
(`domain`, `api/routers/{links,redirect,health}`, `persistence/link_repository`)
and control plane (`orchestration`, `policy`, `persistence/workflow_store`,
`api/routers/{workflows,decisions,metrics}`), sharing only `persistence/db`,
`telemetry`, `config`, `errors`.

Eleven ADRs, all **Accepted** at Gate 4 (`docs/adr/`, `docs/approvals/GATE-4-architecture.md`):
001 modular monolith / two planes · 002 Python 3.12 + FastAPI + Pydantic v2 ·
003 SQLite via SQLAlchemy behind ports · 004 random base62 codes · 005
hand-built DAG + tick scheduler with thread-pool parallelism · 006 state rows
+ append-only event log · 007 gates as graph nodes · 008 retry/timeout/
fallback, safe-stop terminal, rollback-vs-compensation rule · 009 graph-diff
replanning · 010 deterministic agents + isolated run workspace · 011
versioned in-code policy registry. Each records options considered,
consequences, risks, reversibility, traceability and validation.

## 5. API contracts and schema deliverables

- `specs/001-agentic-url-shortener/contracts/openapi.yaml` (OpenAPI 3.1, API
  version 1.0.0) and 12 JSON schemas under `contracts/schemas/`
  (`LinkCreateRequest`, `LinkResponse`, `AnalyticsResponse`, `Problem`,
  `WorkflowCreateRequest`, `WorkflowRunView`, `GraphView`, `GateView`,
  `DecisionRequest`, `DecisionView`, `AuditEventView`, `ArtifactView`).
- **Drift control**: `python scripts/export_contracts.py --check` in
  `scripts/check.sh` and `tests/contract/test_openapi_drift.py` fail when the
  served contract differs from the committed one.
- **Compatibility / migration rule** (plan §2): additive within v1; a
  breaking change requires `/api/v2`, an ADR and change-control approval
  (policy CHG-002, acknowledged at the design-approval gate — see
  `docs/evidence/*/decisions.json` payload `api_change_acknowledged`).
- **Contract tests**: `tests/contract/` (28 tests).
- Persistence schema: `src/agentic_sdlc/persistence/tables.py`; data model
  with versioning rules in `specs/001-agentic-url-shortener/data-model.md`.

## 6. Orchestration model, dependency graph, and state persistence

- **Graph**: built per run by `orchestration/planner.py` from the run
  context; `StageSpec` nodes declare dependencies, owner (agent/human),
  condition, retry policy, timeout, fallback agent, compensability, gate
  policy and emitted artifact kinds (`orchestration/graph.py`). Inspectable:
  `GET /api/v1/workflows/{run_id}/graph`, `docs/evidence/*/graph.json`.
- **Non-linear shape** (verified in evidence): conditional branches
  (`clarification`, `impact_analysis`, `policy_exception` skipped with a
  recorded reason when their condition is false — `events.json`
  `stage_skipped`); parallel fan-out `implement ‖ test_plan ‖ docs_draft`
  with overlapping timestamps; `verify` as the join; sequential
  `security_review → compliance_check` where ordering matters.
- **State machines**: run and stage states and the allowed transition table
  are in `orchestration/states.py`; every transition is unit-tested
  (`tests/unit/test_states.py`, 40 tests); an illegal transition is a
  safe-stop, not a crash (`test_reliability.py::test_illegal_transition_is_a_safe_stop_not_a_crash`).
- **Persistence**: `persistence/workflow_store.py` — run, stage, edge
  (versioned per graph), artifact (with lineage), decision, policy
  evaluation/exception, replan and append-only sequenced event tables.
  Reconstruction from events alone is tested
  (`test_store.py::test_stage_states_can_be_reconstructed_from_events_alone`).
- **Execution**: `orchestration/engine.py` — tick scheduler: compute ready
  set → execute batch on a thread pool (each stage inside its own
  retry/timeout/fallback envelope) → persist → repeat until a gate or terminal
  state. Resume by a fresh engine from persisted state is tested and
  demonstrated (`docs/evidence/resume/`).

## 7. Human approvals, governance gates, and decision lineage

- Gates are graph nodes owned by `human` (ADR-007): `clarification`,
  `design_approval`, `policy_exception`, `release_readiness`.
  `Engine.decide` is the only path past a gate; the scheduler never calls
  it; silence never advances (`tests/orchestration/test_gates.py`, 9 tests,
  including a forged-stage-row attempt).
- Decisions record actor, decision, reason, timestamp, artifact version and
  payload (`GET …/decisions`, `docs/evidence/*/decisions.json`). The API
  requires `X-Actor` (`tests/security/test_security.py::test_decisions_require_an_attributable_actor`).
- Gate timeout → `SAFE_STOPPED / GATE_TIMEOUT` (`docs/evidence/gate-timeout/`).
- Rejection → downstream not executed, compensation in reverse dependency
  order, run `REJECTED` (`docs/evidence/rejection/`); a design rejection with
  `return_to` reworks instead of ending (`tests/e2e/test_scenarios.py::test_design_rejection_with_return_to_reworks_instead_of_ending`).
- Lineage: every artifact carries `derived_from` (upstream artifacts and
  decisions) and `policy_version` (`GET …/lineage`, `artifacts.json`).
- The repository's own lifecycle gates are recorded the same way:
  `docs/approvals/GATE-1…5`.

## 8. Compliance and change-control policy results

Policy registry `src/agentic_sdlc/policy/registry.py`, version **1.0.0**,
recorded on every run (`run.json → policy_version`). Nine policies:
SEC-001 validation controls not weakened · SEC-002 no secrets in artifacts ·
SEC-003 automated security review completed (exceptionable) · CMP-001 every
stage/gate recorded · CMP-002 audit events complete · CHG-001 brownfield
impact analysis before implementation (exceptionable) · CHG-002 API/schema
change acknowledged · DEP-001 dependency allow-list · AUD-001 retention
recorded. Outcomes per run in `docs/evidence/*/policy.json`:

| Run | Result |
|---|---|
| greenfield | 8 PASS, CHG-001 NOT-APPLICABLE |
| brownfield | 9 PASS (CHG-001 PASS — impact analysis preceded implementation) |
| ambiguous | 8 PASS/N-A, SEC-003 EXCEPTION-REQUESTED → approved exception |
| policy-fail | SEC-002 FAIL (injected) → `SAFE_STOPPED / POLICY_BLOCKED`, release **NOT READY** |

Change control: material requirement changes go through replanning with
recorded before/after graphs (§6, §16); API/schema changes need the CHG-002
acknowledgement; the repository's own ADR changes require a superseding ADR
(Gate 4 conditions).

## 9. Policy exceptions, compensating controls, expiry, and approvals

One exception in the evidence: `docs/evidence/ambiguous/policy.json →
exceptions[0]` — policy SEC-003, scope the run, approver `hemant`,
compensating control "manual security checklist reviewed and attached",
approved 2026-10-18, expires 2026-11-17. An unapproved or expired exception
evaluates as FAIL (`tests/unit/test_policy.py`, `tests/unit/test_release.py`).
Non-exceptionable policies (SEC-001, SEC-002, CMP-*) cannot be excepted at all.

## 10. Security controls, findings, and residual risks

Controls (`docs/architecture.md` §6, `tests/security/`, `tests/unit/test_validation.py`):
scheme allow-list; length bound; credentials-in-URL rejected; loopback,
link-local, RFC 1918, ULA and cloud-metadata literal ranges plus a hostname
block-list rejected (parametrised over the full range set); RFC 9457 problem responses without
internals; API key on mutating/workflow endpoints and `X-Actor` on
decisions; API key redacted from structured logs; in-process token-bucket
rate limit with a 429 contract; secret scan of the repository and of workflow
artifacts (SEC-002); `pip-audit` and licence allow-list in the release check.

Findings: none open from the automated checks. Residual risks (accepted,
recorded): no DNS-resolving SSRF check (AMB-03); static API key is not an
identity provider (AMB-06); rate limiting is per process and per key.

## 11. Reliability, retry, fallback, rollback/compensation, and safe-stop

`orchestration/engine.py` + `states.py`, ADR-008, `tests/orchestration/test_reliability.py` (10 tests):
transient vs permanent classification; bounded retry with exponential
backoff and per-attempt timeout (timeout counts as transient); permanent
failures never retried; per-stage fallback agent, result flagged `FALLBACK`;
fallback failure → safe-stop; compensation in reverse dependency order on
rejection; true rollback of workspace writes via recorded inverse operations
(`orchestration/workspace.py`, `tests/orchestration/test_workspace.py`);
safe-stop as a deterministic terminal state with reason (retries exhausted,
gate timeout, policy blocked, illegal transition, operator stop); resume
without re-executing succeeded stages. Demonstrated in
`docs/evidence/{greenfield,ambiguous,rejection,policy-fail,resume,gate-timeout}`.

## 12. MTTR definition, measurement population, calculation, exclusions, and unrecovered failures

`orchestration/metrics.py`, `tests/unit/test_metrics.py`, `docs/evidence/*/metrics.json → recovery`:

- **Definition**: MTTR = total recovery duration across recovered failure
  events ÷ number of recovered failure events.
- **Timestamps captured**: `failure_detected`, `recovery_started`,
  `recovery_completed` events per stage attempt; mechanism recorded
  (`retry`, `fallback`).
- **Population**: stages with a `failure_detected` event in the run.
- **Exclusions**: unrecovered failures are excluded from the denominator and
  reported separately (`recovery.unrecovered`).
- **Demonstration values**: greenfield MTTR 5.22 s (one recovered event, two
  injected transient faults, recovery mechanism retry); ambiguous MTTR 0.01 s
  (one recovered event via fallback). All measurements carry
  `measurement_type: demonstration` and a note; they are not production
  statistics.
- Also reported: stage success/failure rate, retry/timeout/fallback/
  compensation/safe-stop/replan counts, end-to-end latency split into active
  time and human-wait time; aggregate across runs via `GET /api/v1/metrics`.

## 13. Observability, auditability, and evidence integrity

- Structured JSON logs (`telemetry/logging.py`) bound to `run_id`; every
  audit event has sequence, actor type (system/agent/human), kind, stage,
  attempt, result, reason, timestamp (`docs/evidence/*/events.json`).
- Append-only, sequenced event log; duplicate sequence rejected
  (`test_store.py`).
- Evidence export (`agentic-sdlc workflow export-evidence`) writes run,
  graph, events, decisions, artifacts, policy, replans, metrics and a
  human-readable README per run. Committed exports are the candidate's
  actual runs of 2026-10-18; the clean-clone verification
  (`docs/evidence/clean-clone.md`) reproduced all seven terminal states.
- Integrity statements: injected faults are labelled `(demo)` in the event
  reason; scripted scenario decisions are disclosed in every walkthrough; no
  figure in this document is estimated.

## 14. Greenfield well-defined requirement scenario outcome

`docs/scenarios/greenfield.md`, `docs/evidence/greenfield/`. Input: per-link
analytics summary endpoint. Quality checks (completeness, consistency,
testability, boundaries) all passed; the clarification gate was skipped with
the recorded reason "no clarification needed … max ambiguity severity NONE"
(`artifacts.json → quality_check.reason_no_clarification`, `events.json`
seq 9). Decomposition with dependencies and parallel flags; API impact
acknowledged at design approval; parallel fan-out/join; two injected
transient failures recovered by bounded retry; 8 PASS / 1 N-A policies;
terminal `COMPLETED`, release `READY`. Test:
`tests/e2e/test_scenarios.py::test_greenfield_proceeds_without_clarification_with_parallel_fanout_and_retry`.

## 15. Brownfield scenario outcome

`docs/scenarios/brownfield.md`, `docs/evidence/brownfield/`. Input: expired
links return 410 instead of 404 with analytics still readable. The
`impact_analysis` stage ran before decomposition and scanned the actual
repository (164 files, 45 matched), listing impacted modules, control-plane
modules, interfaces, data flows, tests, docs, regression risks, data
compatibility and rollback considerations (`artifacts.json → impact_analysis`).
CHG-001 PASS; terminal `COMPLETED`, release `READY`. The behaviour itself is
implemented and tested in the shortener (FR-U06/U08). Test:
`::test_brownfield_runs_impact_analysis_before_any_change`.

## 16. Ambiguous-requirement scenario outcome

`docs/scenarios/ambiguous.md`, `docs/evidence/ambiguous/`. Input: "Links
should expire after a while and be reusable." Two ambiguities detected
(undefined quantity, HIGH; conflict with FR-U04) with options and impact;
run blocked at `clarification` (`WAITING_CLARIFICATION`) with no downstream
stage ready; human decision recorded (30-day TTL, codes never reused);
requirement revised to v2 and re-checked; **replan v1→v2** with before/after
graphs and 14 invalidated stages (`replans.json`); resumed at
`requirement_revision`, not from the start; every downstream gate
re-decided after the replan; injected permanent security-review failure →
fallback → SEC-003 EXCEPTION-REQUESTED → approved exception with
compensating control and expiry; terminal `COMPLETED`, release `READY WITH
ACCEPTED LIMITATIONS`. Test:
`::test_ambiguous_requirement_blocks_clarifies_replans_and_accepts_exception`.

## 17. Test strategy, executed validation, and actual results

`docs/testing.md`. 290 tests across unit (173), contract (28), integration
(12), orchestration (49), security (18), e2e (7), architecture (3); property
tests with Hypothesis for short-code generation; mypy `--strict` on 60 source
files; ruff lint/format; OpenAPI drift; secret scan; licence allow-list.
Executed results: `./scripts/check.sh` → ALL CHECKS PASSED (≈13 s warm, 25 s
on the clean clone); `docs/evidence/release-check.json` → READY;
`docs/evidence/clean-clone.md`. Test-first is visible in the commit history as
`test(...)` → `feat(...)` pairs.

## 18. Requirement-to-design-to-task-to-code-to-test traceability

`docs/traceability.md`, generated by `python scripts/traceability.py` from
`spec.md` (ids), `tasks.md` (task → requirement/ADR citations and target
paths), `@pytest.mark.req` markers, and `docs/evidence/`. Coverage: every
testable FR/NFR/SCN/SC id has ≥ 1 test; 0 orphan requirements, tasks or
tests; ADR → task → test mapping included. The check runs inside the suite.

## 19. Known limitations, technical debt, and deferred enhancements

Accepted limitations (`docs/testing.md` §3): deterministic rule-based agents
(no LLM; protocol seam provided); single process with thread-pool
parallelism (no multi-process lease); SQLite; literal SSRF check (no DNS
resolution); best-effort analytics (loss on crash); per-process, per-key
rate limit; gate timeouts enforced on the next tick, not by a background
timer; scenario decisions in committed evidence were scripted replays;
brownfield impact analysis is term/symbol based, not semantic; the optional
Dockerfile (AMB-12) was not produced.
Technical debt: `engine.py` is large (~1.2k lines) and would benefit from
splitting the gate, reliability and replanning concerns into modules.
Deferred enhancements: `BACKLOG.md`.

## 20. Repository paths, reproducible commands, and reviewer verification points

`docs/reviewer-guide.md` is the authoritative map (claim → path → command →
expected result → requirement id). Minimum verification path:

```bash
pip install -e ".[dev]" && ./scripts/check.sh                 # ALL CHECKS PASSED, 290 tests
agentic-sdlc scenario run ambiguous --actor you --no-decide    # blocks at the clarification gate
agentic-sdlc workflow gates <run_id>                           # ambiguities + options
agentic-sdlc workflow decide <run_id> clarification clarify --actor you --reason "..." \
  --payload '{"answers": {"AMB-R1": "ttl_30d", "AMB-R2": "reuse_never"}}'
agentic-sdlc workflow events <run_id>                          # replan v2, resume at requirement_revision
agentic-sdlc scenario run policy-fail --actor you              # SAFE_STOPPED, NOT READY
python scripts/release_check.py                                # repository release decision
```

## 21. Final engineering judgment, unresolved blockers, and recommended next actions

**Judgment**: the assignment's differentiator — governed, stateful,
non-linear orchestration with real gates, bounded reliability controls,
replanning and audit-grade evidence — is implemented, tested, and
demonstrated with executable evidence rather than described. The deliberate
trade-off was depth in the control plane over breadth in the shortener and
determinism over LLM realism; both are recorded decisions with the seam to
reverse them.

**Unresolved blockers**: none. Mandatory findings from the independent
assessment (`docs/reviews/final-assessment.md`) were dispositioned in
`docs/approvals/GATE-5-release-readiness.md`.

**Recommended next actions** (in order): (1) LLM agent adapter behind the
`Agent` protocol with artifact-schema validation, re-recording the three
scenarios; (2) stage lease column + store-backed queue for multi-process
execution; (3) DNS-resolving SSRF check with negative caching; (4) analytics
outbox; (5) split `engine.py` by concern; (6) OTLP export of stage spans.
