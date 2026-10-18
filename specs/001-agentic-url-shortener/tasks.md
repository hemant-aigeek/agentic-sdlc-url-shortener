# Tasks: Agentic Software Engineering System — URL Shortener

**Feature**: `001-agentic-url-shortener` | **Plan**: [plan.md](plan.md) | **Date**: 2026-10-18

Conventions: `[P]` = may run in parallel with other `[P]` tasks in the same
group (no shared files, no unresolved interfaces). `TDD` = failing test is
written and executed before the implementation. `Gate` = human decision
required before the task is considered complete. Every task cites the
requirement and ADR identifiers it serves; `tests/` markers (`@pytest.mark.req`)
carry the same IDs so `docs/traceability.md` can be generated.

Validation command for every implementation task unless stated otherwise:
`./scripts/check.sh` (ruff + mypy + pytest + contract drift + secret scan).

## Timebox and scope control (TB)

| ID | Task | Owner |
|---|---|---|
| TB-01 | Must-have scope = plan §12 slices 1–9. Deferred scope listed in `BACKLOG.md`. | human |
| TB-02 | Day milestones: D1 = G0–G1 green; D2 = G2–G5 green; D3 = G6–G9 + submission. | human |
| TB-03 | Checkpoint after every group: run checkpoint review, commit, push. Do not start the next group with a red suite. | human |
| TB-04 | Stop condition: if G7 (scenarios) is not green by D3 midday, drop SCN-C fault injection (keep clarification + replan) and move the rejection demo to tests only. | human |
| TB-05 | Critical path: G1 → G2 → G3 → G4 → G5 → G7 → G9. G6 and G8 can overlap with G7. | — |

## G0 — Engineering baseline (slice 1)

| ID | Task | Deps | Reqs / ADRs | Notes |
|---|---|---|---|---|
| T-001 | `pyproject.toml` with runtime + dev deps, ruff/mypy/pytest config, markers incl. `req`. | — | NFR-08, NFR-09, ADR-002 | done |
| T-002 | `tests/conftest.py`; `tests/architecture/test_import_rules.py` (import direction, nothing imports api/cli). | T-001 | NFR-08, ADR-001 | TDD (red until G1) |
| T-003 | `scripts/check.sh`: ruff check+format --check, mypy, pytest -q, contract drift, licence allow-list, secret-pattern scan. | T-001 | NFR-08, NFR-12, SEC-002 | |
| T-004 | `README.md` skeleton: objective, setup, commands; `BACKLOG.md`; `.env.example`. | T-001 | NFR-12 | docs evolve with code |

## G1 — Walking skeleton (slice 2)

| ID | Task | Deps | Reqs / ADRs | Notes |
|---|---|---|---|---|
| T-010 | `tests/integration/test_health.py`: live/ready/ready-fail/problem-404. | T-002 | FR-U12, FR-U13 | TDD, red |
| T-011 | `config.py` Settings (env-driven: database_url, api_key, data_dir, retry defaults, gate timeouts, demo-fault flags). | T-001 | NFR-12 | |
| T-012 | `errors.py` exception hierarchy (ValidationError, NotFound, Gone, Conflict, StoreUnavailable, StageError(kind), IllegalTransition, GateRequired). | T-011 | FR-U13, FR-O05, FR-O08 | |
| T-013 | `persistence/db.py` Database (engine, session factory, `create_all`, `schema_version`, `ping`). `persistence/tables.py` app-plane tables. | T-012 | ADR-003, data-model | |
| T-014 | `api/problems.py` RFC 9457 problem+json + exception handlers (no stack traces); `api/app.py` factory with correlation-id middleware; `api/routers/health.py`. | T-012, T-013 | FR-U12, FR-U13, NFR-04 | makes T-010 green |
| T-015 | `telemetry/logging.py` structlog JSON with run_id/stage binding and key redaction. | T-011 | NFR-01, NFR-04 | |
| T-016 | `cli.py` Typer app: `serve`, `init-db`. | T-014 | NFR-12 | |
| T-017 | Checkpoint G1: suite green, `check.sh` green, commit `feat(api): walking skeleton with health and problem responses`. | T-010..T-016 | — | Gate: none |

## G2 — Core URL behaviour (slice 3)

| ID | Task | Deps | Reqs / ADRs | Notes |
|---|---|---|---|---|
| T-020 | `tests/unit/test_validation.py`: scheme allow-list, host present, length, loopback/link-local/private/ULA/metadata literals, hostname block-list, normalisation. | T-017 | FR-U02, FR-U03, NFR-01 | TDD [P] |
| T-021 | `tests/unit/test_codes.py`: length 7, alphabet, uniqueness over 10k, hypothesis property. | T-017 | FR-U04, ADR-004 | TDD [P] |
| T-022 | `domain/validation.py`, `domain/codes.py`. | T-020, T-021 | FR-U02..U04 | green |
| T-023 | `tests/unit/test_service.py` with in-memory fake repos: create, resolve, expired→Gone, unknown→NotFound, idempotency same/different payload, collision regeneration bounded, store failure→StoreUnavailable, analytics summary. | T-022 | FR-U01, U05..U09, U11 | TDD |
| T-024 | `domain/models.py`, `domain/ports.py`, `domain/service.py`. | T-023 | FR-U01..U11 | green |
| T-025 | `tests/integration/test_link_repository.py`: SQLite repos, unique constraints, concurrent creates (threads) yield distinct codes, analytics per-day grouping. | T-024 | FR-U10, NFR-05 | TDD |
| T-026 | `persistence/link_repository.py` (ShortLinkRepository, AnalyticsRepository). | T-025 | ADR-003 | green |
| T-027 | `tests/contract/test_links_api.py`: POST create (201, schema), invalid → 422 problem with field errors, GET redirect 307, unknown 404, expired 410, analytics 200, idempotency 200/409, API key 401, rate limit 429. | T-026 | FR-U01..U13, AMB-06, AMB-07 | TDD |
| T-028 | `api/auth.py`, `api/ratelimit.py`, `api/routers/{links,redirect,analytics}.py`, `api/deps.py`; best-effort analytics recorder. | T-027 | FR-U01..U13 | green |
| T-029 | `tests/contract/test_openapi_drift.py` + `contracts/openapi.yaml` export script; `contracts/schemas/*.json`. | T-028 | plan §2, CHG-002 | TDD |
| T-030 | Checkpoint G2: green; commit progression `test(api)…` → `feat(api)…` → `feat(analytics)…`. | T-020..T-029 | — | |

## G3 — Orchestration state model (slice 4)

| ID | Task | Deps | Reqs / ADRs | Notes |
|---|---|---|---|---|
| T-040 | `tests/unit/test_states.py`: every allowed transition passes; a sample of illegal ones raise `IllegalTransition`; terminal states have no exits. | T-017 | FR-O05, ADR-006 | TDD [P] |
| T-041 | `tests/unit/test_graph.py`: validate (no cycles, deps exist), ready-set computation, join waits for all, conditional edges, downstream closure, diff old/new. | T-017 | FR-O02..O04, FR-O14, ADR-005, ADR-009 | TDD [P] |
| T-042 | `orchestration/states.py`, `orchestration/graph.py`, `orchestration/policies.py`. | T-040, T-041 | FR-O02..O05, O08, O09 | green |
| T-043 | `tests/orchestration/test_store.py`: persist/load run, stages, edges, events append-only (no update API), artifacts with lineage, decisions; reconstruction of stage states from events alone. | T-042 | FR-O06, FR-O07, NFR-04, NFR-05 | TDD |
| T-044 | `orchestration/store.py` protocol, `orchestration/events.py`, `orchestration/context.py`, `persistence/workflow_store.py` + control-plane tables. | T-043 | ADR-006 | green |
| T-045 | `tests/orchestration/test_engine_basic.py`: start run → stages execute in dependency order; two independent stages overlap in time (parallel); join starts only after both; condition false → SKIPPED; stage outputs available to dependants (context). | T-044 | FR-O01, O03, O04, SC-04 | TDD |
| T-046 | `orchestration/agents/base.py` (Agent protocol, StageResult), `orchestration/engine.py` (start, tick loop, thread-pool execution, persistence of results). | T-045 | ADR-005 | green |
| T-047 | Checkpoint G3; commit `feat(orchestration): establish workflow state and dependency model`. | T-040..T-046 | — | |

## G4 — Approval governance (slice 5)

| ID | Task | Deps | Reqs / ADRs | Notes |
|---|---|---|---|---|
| T-050 | `tests/orchestration/test_gates.py`: engine stops at human-owned stage (WAITING_APPROVAL); tick without decision does not advance; `decide(approve)` advances; `decide(reject)` → downstream not executed, compensation of side-effecting stages in reverse order, run REJECTED; decision record has actor/reason/timestamp/artifact version; gate timeout → SAFE_STOPPED(GATE_TIMEOUT); agents cannot call transition past a gate. | T-047 | FR-G01..G05, NFR-11, ADR-007 | TDD |
| T-051 | Gate handling in `engine.py` (`decide`, `open_gate`, timeout check), decision persistence, compensation ordering. | T-050 | ADR-007, ADR-008 | green |
| T-052 | `tests/contract/test_workflow_api.py`: create run, inspect run/graph/events/artifacts, list gates, POST decision (auth + actor header required), resume, stop. | T-051 | FR-O01, O02, O20, FR-G02, G03 | TDD |
| T-053 | `api/routers/{workflows,decisions}.py`. | T-052 | — | green |
| T-054 | Checkpoint G4; commit `feat(governance): enforce human approval transitions`. | T-050..T-053 | — | |

## G5 — Reliability controls (slice 6)

| ID | Task | Deps | Reqs / ADRs | Notes |
|---|---|---|---|---|
| T-060 | `tests/orchestration/test_reliability.py`: transient failure retried with backoff and recorded attempts; permanent failure not retried; per-attempt timeout → TRANSIENT; exhaustion with fallback → FALLBACK state, flagged result; exhaustion without fallback → SAFE_STOPPED(RETRIES_EXHAUSTED); idempotent re-execution of SUCCEEDED stage is a no-op; illegal transition → SAFE_STOPPED(ILLEGAL_TRANSITION); operator stop. | T-054 | FR-O08..O12, NFR-02, ADR-008 | TDD |
| T-061 | Retry/timeout/fallback/safe-stop in `engine.py`; `telemetry/timing.py`. | T-060 | — | green |
| T-062 | `tests/orchestration/test_workspace.py`: apply ChangeSet creates/modifies files under `data/runs/<id>/workspace`; revert restores exact prior content (rollback); never touches repo root; compensation action recorded and executed for non-reversible stage. | T-061 | FR-O11, AMB-10, ADR-010 | TDD |
| T-063 | `orchestration/workspace.py`; compensation protocol on agents. | T-062 | — | green |
| T-064 | `tests/orchestration/test_resume.py`: new Engine instance over same store resumes at WAITING_APPROVAL; RUNNING stage found at load → RETRYING if eligible; succeeded stages not re-run; resume event recorded. | T-063 | FR-O13, NFR-03 | TDD |
| T-065 | `Engine.resume`, `Engine.stop`. | T-064 | — | green |
| T-066 | Checkpoint G5; commits `feat(resilience): …`, `feat(recovery): …`. | T-060..T-065 | — | |

## G6 — Observability and metrics (slice 7)

| ID | Task | Deps | Reqs / ADRs | Notes |
|---|---|---|---|---|
| T-070 | `tests/unit/test_metrics.py`: from a synthetic event list compute success/failure rates, retry/fallback/compensation/safe-stop counts, recovery durations, MTTR (recovered only), unrecovered count, e2e latency; measurement_type == "demonstration". | T-066 | FR-O19, plan §5 | TDD [P] |
| T-071 | `orchestration/metrics.py`; `api/routers/metrics.py`; `GET /workflows/{id}/lineage`. | T-070 | FR-O07, O19 | green |
| T-072 | `cli.py`: `inspect`, `events`, `metrics`, `export-evidence` (JSON + markdown summary into `docs/evidence/<run_id>/`). | T-071 | SC-02, NFR-12 | |
| T-073 | Checkpoint G6; commit `feat(observability): add workflow audit events and metrics`. | T-070..T-072 | — | |

## G7 — Agents, planner, policy, scenarios (slice 8)

| ID | Task | Deps | Reqs / ADRs | Notes |
|---|---|---|---|---|
| T-080 | `tests/unit/test_policy.py`: registry has POLICY_VERSION; each policy yields exactly one of four outcomes; mandatory FAIL blocks; approved unexpired exception unblocks; expired/unapproved behaves as FAIL; evaluation records version. | T-073 | FR-G06..G09, ADR-011 | TDD [P] |
| T-081 | `policy/{model,registry,evaluator}.py` (SEC-001, SEC-002, CMP-001, CMP-002, CHG-001, CHG-002, DEP-001, AUD-001). | T-080 | — | green |
| T-082 | `tests/unit/test_agents.py`: ingest normalises; quality check scores completeness/consistency/testability/boundaries and detects ambiguity with severity; impact analysis reads the real repository and lists impacted modules/tests/docs; decompose yields tasks with deps; design flags API/schema impact. | T-073 | FR-O15..O18, SCN-B | TDD [P] |
| T-083 | `orchestration/agents/{ingest,quality,impact,decompose,design,implement,testplan,docs,verify,security,compliance,release,summary}.py`. | T-082, T-081 | ADR-010 | green |
| T-084 | `tests/orchestration/test_planner.py`: greenfield graph has no clarification/impact nodes; brownfield has impact_analysis before decompose; ambiguous has clarification gate; fan-out groups and joins present in all. | T-083 | FR-O02, O04, SCN-A/B/C | TDD |
| T-085 | `orchestration/planner.py`. | T-084 | — | green |
| T-086 | `tests/orchestration/test_replan.py`: clarification decision bumps requirement version, invalidates downstream closure, regenerates artifacts (version+1), records ReplanEvent with before/after graph, resumes from first invalidated stage, does not re-run unaffected stages, re-arms downstream gates. | T-085 | FR-O14, ADR-009 | TDD |
| T-087 | `Engine.replan`. | T-086 | — | green |
| T-088 | `tests/e2e/test_scenarios.py`: SCN-A straight through with recorded "no clarification needed" reason, parallel group visible, retry evidence; SCN-B impact artifact precedes implement, CHG-001 PASS, regression executed; SCN-C blocks, clarifies, replans, resumes, fallback → exception gate → READY WITH ACCEPTED LIMITATIONS; plus rejection→compensation and restart→resume demos. | T-087 | SCN-A/B/C, SC-02, SC-04..06 | TDD |
| T-089 | `scenarios/*.py`, `cli.py run-scenario`/`decide`, demo-fault injection via Settings. | T-088 | — | green |
| T-090 | Execute the three scenarios via CLI; export evidence to `docs/evidence/`; commit `test(scenarios): …` ×3. | T-089 | SC-02 | Gate: clarification + approvals are given by the human in the CLI |
| T-091 | Checkpoint G7. | T-080..T-090 | — | |

## G8 — Security and release checks

| ID | Task | Deps | Reqs / ADRs | Notes |
|---|---|---|---|---|
| T-100 | `tests/security/test_security.py`: no secrets/API key in logs or events; problem responses contain no traceback; open-redirect abuse cases rejected; approval endpoint without actor header → 401. | T-054 | NFR-01, SEC-002 | TDD [P] |
| T-101 | `scripts/release_check.py`: pip-audit, pip-licenses allow-list, secret scan, full suite, policy summary → `docs/evidence/release-check.json`. | T-100 | FR-G10, constitution V | |
| T-102 | Release-readiness demonstration: one run with an injected mandatory policy FAIL → NOT READY (evidence committed). | T-089, T-101 | SC-06 | |

## G9 — Documentation, traceability, submission

| ID | Task | Deps | Reqs / ADRs | Notes |
|---|---|---|---|---|
| T-110 | `docs/architecture.md` (planes, modules, control flow diagram, state machines, key decisions, threat notes, scaling path). | T-091 | deliverable 2 | [P] |
| T-111 | `docs/scenarios/{greenfield,brownfield,ambiguous}.md` with evidence links. | T-090 | deliverable 3 | [P] |
| T-112 | `docs/testing.md` (approach, levels, what is demonstrated vs claimed, limitations, trade-offs). | T-091 | deliverable 5 | [P] |
| T-113 | `scripts/traceability.py` → `docs/traceability.md` from `req` markers + tasks.md. | T-091 | SC-03, NFR-09 | |
| T-114 | `docs/reviewer-guide.md` (claim → path → command → expected result). | T-110..T-113 | guide §26 | |
| T-115 | `docs/final-engineering-summary.md` (21-section schema). | T-114 | deliverable / requirement 8 | |
| T-116 | Independent hostile review (fresh session, no edits) → `docs/reviews/final-assessment.md`; fix mandatory findings. | T-115 | guide §23 | Gate: human disposition |
| T-117 | Clean-clone verification on a fresh checkout; record output in `docs/evidence/clean-clone.md`. | T-116 | NFR-12, SC-01 | |
| T-118 | Release decision record `docs/approvals/GATE-5-release-readiness.md`; tag `assessment-submission-v1.0`; push. | T-117 | FR-G10 | Gate: human |

## Dependency summary

```
G0 ─► G1 ─► G2 ─┐
            └─► G3 ─► G4 ─► G5 ─► G6 ─► G7 ─► G9
                            └──────► G8 ──┘
```
G2 and G3 are independent after G1 and may be interleaved; G8 may start after
G4. All human-gate tasks (T-090, T-116, T-118) block on a recorded decision.
