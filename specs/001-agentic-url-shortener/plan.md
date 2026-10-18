# Implementation Plan: Agentic Software Engineering System — URL Shortener

**Feature**: `001-agentic-url-shortener` | **Date**: 2026-10-18 | **Spec**: [spec.md](spec.md)
**Status**: Approved at Gate 4 together with ADR-001..ADR-011 (see `docs/approvals/GATE-4-architecture.md`)

## Summary

Two planes in one Python process:

- **Application plane** — a small, production-disciplined URL shortener
  (create / redirect / expire / analytics / health) exposed over HTTP.
- **Control plane** — an orchestration engine that takes a software
  requirement and drives it through an explicit SDLC dependency graph
  (ingest → quality check → [clarification] → [impact analysis] → decompose →
  design → *design approval* → {implement ‖ test plan ‖ docs} → verify →
  {security ‖ compliance} → *release readiness* → summary) with persisted
  state, parallel fan-out/join, conditional branches, human gates, bounded
  retries, fallback, compensation, safe-stop, resume, and dynamic replanning.

Agents are deterministic stage executors behind an `Agent` protocol (Gate 3,
AMB-08). The implementation agent works in an isolated **run workspace**, never
the live repository; promoting a change set into the repository is a human act.
That boundary *is* the controlled-autonomy model.

## Technical Context

| | |
|---|---|
| **Language/Version** | Python ≥ 3.12 (developed and verified on 3.12 and 3.13) |
| **Primary dependencies** | FastAPI, Pydantic v2, SQLAlchemy 2.x (sync), uvicorn, Typer (CLI), structlog |
| **Storage** | SQLite (file-backed; in-memory for tests) via SQLAlchemy Core/ORM |
| **Testing** | pytest, pytest-cov, httpx (TestClient), hypothesis (code generation properties) |
| **Quality tooling** | ruff (lint+format), mypy (strict on `src/`), pip-audit, pip-licenses, a secret-pattern scan script |
| **Target platform** | Local developer machine (Linux/macOS/Windows); optional Dockerfile |
| **Project type** | Single package (`src/agentic_sdlc`) with web API + CLI |
| **Performance goals** | Redirect p95 < 50 ms locally (AS-02, demonstration measurement) |
| **Constraints** | Single process, no external services, full suite < 2 min (AS-03), clean-clone runnable (NFR-12) |
| **Scale/Scope** | Assessment prototype; scaling path documented, not built (AS-04) |

## Constitution Check

| Principle | How the plan complies | Status |
|---|---|---|
| I Spec before code | Every module below maps to FR/NFR IDs; tasks cite them. | PASS |
| II Explicit orchestration | `orchestration/graph.py` is a real DAG with join/branch/replan; scheduler executes ready sets concurrently. | PASS |
| III Human governance | Gates are graph nodes owned by `human`; engine cannot transition them; timeout → `SAFE_STOPPED`. | PASS |
| IV TDD | Task plan orders failing test → implementation for domain and orchestration; checkpoint prompt requires executed validation. | PASS |
| V Security | `domain/validation.py` scheme allow-list + private-range rejection; problem responses without stack traces; secret scan in release check. | PASS |
| VI Policy enforcement | `policy/` versioned registry; evaluation at `compliance_check` and `release_readiness`; FAIL blocks. | PASS |
| VII Architecture | Seven modules with import-direction rule enforced by a test. | PASS |
| VIII Reliability | Per-stage `RetryPolicy`/`TimeoutPolicy`/fallback/compensate; safe-stop terminal; resume from store. | PASS |
| IX Observability | Correlation ID in log context + every event; reconstruction test. | PASS |
| X Traceability | `docs/traceability.md` generated from test markers + task IDs. | PASS |
| XI Evidence | Scenario runs export evidence to `docs/evidence/`; demo data labelled. | PASS |

No violations → Complexity Tracking table not required.

## Project Structure

### Documentation (this feature)

```text
specs/001-agentic-url-shortener/
├── spec.md              # approved requirements
├── plan.md              # this file
├── research.md          # technology evaluation summary (feeds ADRs)
├── data-model.md        # entities, tables, state machines
├── quickstart.md        # reviewer run-through
├── contracts/
│   ├── openapi.yaml     # v1 HTTP contract (exported from the app, drift-tested)
│   └── schemas/         # workflow-state, event, decision, policy JSON schemas
├── checklists/          # /speckit.checklist output
└── tasks.md             # /speckit.tasks output
docs/
├── adr/                 # ADR-001..ADR-011
├── approvals/           # human gate records
├── architecture.md      # overview, planes, control flow, key decisions
├── scenarios/           # walkthroughs A/B/C with evidence links
├── evidence/            # executed run exports (labelled demonstration data)
├── testing.md           # approach, levels, limitations, trade-offs
├── traceability.md      # requirement → … → evidence matrix
├── reviewer-guide.md    # navigation: claim → path → command → expected result
└── final-engineering-summary.md
```

### Source code

```text
src/agentic_sdlc/
├── __init__.py
├── config.py                 # Settings (env-driven), feature flags for demo faults
├── errors.py                 # domain + orchestration exception hierarchy
├── domain/                   # application-plane domain (no I/O)
│   ├── models.py             # ShortLink, RedirectEvent, AnalyticsSummary
│   ├── validation.py         # URL normalisation, scheme allow-list, private-range rules
│   ├── codes.py              # base62 random code generator (FR-U04)
│   ├── ports.py              # ShortLinkRepository / AnalyticsRepository protocols
│   └── service.py            # ShortenerService (create/resolve/analytics/idempotency)
├── persistence/
│   ├── db.py                 # engine/session factory, migrations-lite (create_all + version table)
│   ├── tables.py             # SQLAlchemy table definitions (app + control plane)
│   ├── link_repository.py    # SQLite implementations of domain ports
│   └── workflow_store.py     # SQLite implementation of orchestration.store.WorkflowStore
├── api/
│   ├── app.py                # FastAPI factory, middleware (correlation id, problem handler)
│   ├── deps.py               # DI: settings, session, services, engine
│   ├── auth.py               # API key + actor header (AMB-06)
│   ├── ratelimit.py          # in-process token bucket (AMB-07)
│   ├── problems.py           # RFC 9457 problem+json responses (FR-U13)
│   └── routers/
│       ├── links.py          # POST /api/v1/links, GET /api/v1/links/{code}
│       ├── redirect.py       # GET /{code}
│       ├── analytics.py      # GET /api/v1/links/{code}/analytics
│       ├── health.py         # /health/live, /health/ready
│       ├── workflows.py      # create/inspect/graph/events/artifacts/resume/stop
│       ├── decisions.py      # gates listing + POST decision
│       └── metrics.py        # /api/v1/metrics, /api/v1/policies
├── orchestration/
│   ├── states.py             # RunState, StageState, allowed-transition tables
│   ├── graph.py              # StageSpec, Edge, WorkflowGraph (validate, ready set, downstream closure, diff)
│   ├── policies.py           # RetryPolicy, TimeoutPolicy, GatePolicy, FailureKind
│   ├── context.py            # RunContext: requirement, artifacts, decisions, lineage, workspace
│   ├── events.py             # AuditEvent, EventKind, emitter
│   ├── store.py              # WorkflowStore protocol (persist/load run, stages, events, artifacts, decisions)
│   ├── workspace.py          # Workspace: apply/revert ChangeSet in data/runs/<id>/workspace
│   ├── engine.py             # Engine: start, tick, execute_stage, decide, resume, stop, replan
│   ├── planner.py            # build_graph(ctx) -> WorkflowGraph (conditional on scope/ambiguity)
│   ├── metrics.py            # success/failure/retry/fallback/compensation/MTTR/latency from events
│   └── agents/
│       ├── base.py           # Agent protocol: execute(ctx) -> StageResult; compensate(ctx)
│       ├── ingest.py         # requirement normalisation
│       ├── quality.py        # completeness/consistency/testability/boundary checks, ambiguity detection
│       ├── impact.py         # brownfield impact analysis (reads repository)
│       ├── decompose.py      # tasks with dependencies
│       ├── design.py         # design + API/schema impact
│       ├── implement.py      # applies ChangeSet to workspace (compensable)
│       ├── testplan.py       # test plan artifact
│       ├── docs.py           # documentation draft artifact
│       ├── verify.py         # runs pytest in the workspace (subprocess, timeout)
│       ├── security.py       # security review (fallback: manual review → EXCEPTION-REQUESTED)
│       ├── compliance.py     # policy evaluation stage
│       ├── release.py        # release-readiness determination
│       └── summary.py        # final engineering summary artifact
├── policy/
│   ├── model.py              # Policy, Outcome, PolicyEvaluation, PolicyException
│   ├── registry.py           # POLICY_VERSION + policy definitions (SEC/CMP/CHG/DEP)
│   └── evaluator.py          # evaluate(ctx) -> evaluations; blocking logic; exception handling
├── telemetry/
│   ├── logging.py            # structlog config, correlation-id binding
│   └── timing.py             # monotonic timers for latency/MTTR
├── scenarios/
│   ├── loader.py             # scenario definitions (requirement text, change sets, faults)
│   ├── greenfield.py         # SCN-A
│   ├── brownfield.py         # SCN-B
│   └── ambiguous.py          # SCN-C
└── cli.py                    # agentic-sdlc: serve, run-scenario, decide, resume, inspect, metrics, export-evidence

tests/
├── unit/                     # domain, graph, states, policies, metrics
├── contract/                 # OpenAPI drift, schema validation, problem format
├── integration/              # API + SQLite, persistence, resume after restart
├── orchestration/            # transitions, fan-out/join, retry, timeout, fallback, compensation, safe-stop, resume, replan, gates
├── security/                 # URL validation, private ranges, secret leakage, auth
├── e2e/                      # three scenarios end-to-end through CLI/engine
└── architecture/             # import-direction and no-cycle rules (NFR-08)
```

**Structure decision**: single installable package with a `src/` layout; the
two planes are separate sub-packages that share only `persistence/` and
`telemetry/`. Import rule (tested): `domain` imports nothing internal;
`orchestration` may import `policy`, `telemetry`; `api` may import everything;
nothing imports `api` or `cli`.

## 1. System Context

- **Boundary**: one process exposing an HTTP API and a CLI; one SQLite file.
- **Actors**: API consumer (links), software engineer (submits requirements),
  human reviewer/approver (decisions), release owner (readiness), assessment
  reviewer (verifies), operator (resume/stop).
- **External dependencies**: none at runtime. `verify` spawns a local `pytest`
  subprocess.
- **Trust boundaries**: (1) public redirect path — unauthenticated, read-only;
  (2) mutating link API — API key; (3) workflow + decision API — API key +
  actor header; (4) run workspace — filesystem under `data/runs/`, never the
  repository.
- **Data ownership**: application plane owns `short_links`, `redirect_events`;
  control plane owns `workflow_*`, `policy_*`. No cross-plane foreign keys.

## 2. URL Shortener Architecture

- **API v1** (`/api/v1`), versioned in path; `GET /{code}` is unversioned by
  design (short links must be stable). OpenAPI exported to
  `contracts/openapi.yaml`; a contract test fails on drift so any change is a
  reviewed commit.
- **Schemas**: `LinkCreateRequest`, `LinkResponse`, `AnalyticsResponse`,
  `Problem`, plus control-plane `WorkflowRun`, `StageView`, `GraphView`,
  `AuditEvent`, `Decision`, `PolicyEvaluation`, `Metrics`. Schema version is
  carried in `x-schema-version` on each model and exported as JSON Schema to
  `contracts/schemas/`.
- **Compatibility rule**: additive changes within v1; a breaking change
  requires `/api/v2`, an ADR, and change-control approval (policy CHG-002).
- **Short codes**: 7-char base62 from `secrets.token_bytes`; bounded
  regeneration on unique-constraint violation (AMB-02, FR-U04).
- **Validation**: parse → scheme ∈ {http, https} → host present → length ≤ 2048
  → host not in {localhost, *.localhost, *.internal} → literal IP not in
  loopback/link-local/private/ULA/metadata ranges (AMB-03, FR-U02/U03).
- **Expiration**: `expires_at` optional, must be future at creation; resolve
  returns 410 when past (FR-U06).
- **Analytics**: `RedirectEvent` written by a best-effort recorder after the
  redirect response is prepared; failure is logged, never raised (AMB-05).
  Summary = total, first/last, per-day counts (FR-U08).
- **Idempotency**: `idempotency_key` unique column with payload hash; same
  key + same hash → existing; same key + different hash → 409 (FR-U09).
- **Health**: live = process up; ready = `SELECT 1` succeeds (FR-U12).
- **Rate limit**: token bucket keyed by API key on `POST /api/v1/links` (AMB-07).

## 3. Agentic Orchestration Architecture

### Graph (built per run by `planner.build_graph(ctx)`)

```text
ingest ──► quality_check ──┬─(ambiguity ≥ HIGH)──► clarification [HUMAN] ──► (replan) ──┐
                           └─(clear)───────────────────────────────────────────────────┤
                                                                                        ▼
                                   (brownfield) impact_analysis ──► decompose ──► design ──► design_approval [HUMAN]
                                   (greenfield) ────────────────► decompose ──► design ──► design_approval [HUMAN]
                                                                                        │
                                              ┌────────────── fan-out ──────────────────┤
                                              ▼              ▼              ▼           │
                                          implement      test_plan      docs_draft      │
                                              └──────────── join ───────────┘           │
                                                             ▼                          │
                                                          verify  (retry-eligible)      │
                                              ┌───────── fan-out ──────────┐            │
                                              ▼                            ▼            │
                                      security_review              compliance_check     │
                                      (fallback → manual)         (policy eval, blocks) │
                                              └──────────── join ──────────┘            │
                                                             ▼                          │
                                                 release_readiness [HUMAN] ◄────────────┘
                                                             ▼
                                                          summary
```

Every node is a `StageSpec` with: `name`, `agent`, `owner` (`agent` |
`human`), `depends_on`, `condition` (callable on context), `retry`,
`timeout`, `fallback`, `compensate`, `emits`. Prohibited transitions are
anything not in the transition table in `states.py`; the engine raises and
safe-stops on an attempt.

### Scheduler

`Engine.run(run_id)` is a loop: load run → compute ready set (all hard
dependencies `SUCCEEDED` or `FALLBACK`, condition true, stage `PENDING`) →
submit ready agent-owned stages to a thread pool → persist each result as it
completes → repeat. The loop exits when a human-owned stage becomes ready
(run → `WAITING_APPROVAL` / `WAITING_CLARIFICATION`), when the graph is
exhausted (`COMPLETED`), or on `SAFE_STOPPED` / `FAILED` / `REJECTED`.
Parallelism is visible as overlapping `started_at`/`ended_at` on sibling
stages and a `parallel_group` tag on their events.

### Human-in-the-loop

Gates: `clarification`, `design_approval`, `release_readiness`, plus
on-demand `policy_exception` and `risk_acceptance` gates raised by
`compliance_check`/`security_review`. `Engine.decide(run_id, gate, actor,
decision, reason, payload)` is the only way past a gate. `reject` → compensate
side-effecting stages in reverse order → `REJECTED`. Gate timeout (if set) →
`SAFE_STOPPED(GATE_TIMEOUT)`.

### Reliability

| Concern | Mechanism |
|---|---|
| Transient vs permanent | `StageError(kind=TRANSIENT|PERMANENT)`; agents classify; timeouts are TRANSIENT |
| Retry | `RetryPolicy(max_attempts, base_delay, multiplier, max_delay)`; attempts recorded as events |
| Timeout | per-attempt `TimeoutPolicy(seconds)` enforced via future timeout; `verify` also passes it to the subprocess |
| Fallback | `StageSpec.fallback` agent runs after exhaustion; stage ends `FALLBACK`, result flagged |
| Rollback vs compensation | `implement` applies a `ChangeSet` to the workspace and records inverse operations; revert = rollback (files restored). Stages with non-reversible effects (e.g. a recorded external notification in tests) register a compensating action |
| Safe-stop | triggers: exhaustion without fallback, gate timeout, mandatory policy FAIL without exception, illegal transition, operator stop. Terminal, reason recorded |
| Idempotency | stage execution keyed by `(run_id, stage, attempt)`; re-running a `SUCCEEDED` stage is a no-op |
| Resume | `Engine.resume(run_id)` rebuilds in-memory state from the store; `RUNNING` stages found at load are treated as interrupted → `RETRYING` if eligible |

### Dynamic replanning

Trigger: a gate decision that changes an upstream artifact (clarification,
design rejection with `return_to`), or an explicit requirement update. Steps:
(1) snapshot current graph; (2) apply the change to context; (3)
`planner.build_graph(ctx)` again; (4) `graph.diff(old, new)` yields
added/removed/changed stages; (5) downstream closure of changed stages →
`INVALIDATED`, artifacts versioned up; (6) `ReplanEvent(before, after,
reason)` persisted; (7) run returns to `RUNNING` from the first invalidated
stage. Gates downstream of the change are re-armed — replanning never skips a
gate.

## 4. State and Decision Lineage

Persisted per run: requirement (raw + normalised, versioned), graph (as
built, and every replan version), stage states with attempts, artifacts
(`kind`, `version`, `content`, `derived_from[]`, `policy_version`), decisions,
policy evaluations/exceptions, events (append-only, sequence-numbered),
metrics snapshot at terminal state. `GET /workflows/{id}/lineage` walks
`derived_from` from the summary back to the requirement.

## 5. Observability

- structlog JSON logs bound with `run_id`, `stage`, `attempt`.
- Events are the system of record for reconstruction (NFR-04 test rebuilds
  stage states from events only).
- Metrics (`orchestration/metrics.py`) computed from events, exposed at
  `/api/v1/metrics` and by `agentic-sdlc metrics`. MTTR = Σ recovery duration ÷
  recovered failure count; `failure_detected`, `recovery_started`,
  `recovery_completed` timestamps are explicit event kinds; unrecovered
  failures reported separately. Every export carries
  `"measurement_type": "demonstration"`.

## 6. Security

Input validation and private-range rejection (above); API key + actor header;
problem responses never include stack traces; structlog processors redact
`api_key`/`authorization`; secret-pattern scan over artifacts (SEC-002) and
over the repo in release check; `pip-audit` + `pip-licenses` in release check;
threat notes in `docs/architecture.md` (open redirect abuse, SSRF via
redirector, enumeration, analytics poisoning, approval spoofing).

## 7. Compliance and Change Control

`policy/registry.py` `POLICY_VERSION = "1.0.0"`:

| ID | Domain | Mandatory | Check |
|---|---|---|---|
| SEC-001 | security | yes | change set and design do not weaken URL validation (allow-list present) |
| SEC-002 | security | yes | no secret patterns in artifacts |
| CMP-001 | compliance | yes | every executed stage has start/end events; every gate has a decision |
| CMP-002 | compliance | yes | audit events carry actor, action, timestamp, target, result |
| CHG-001 | change control | yes | brownfield runs have an `impact_analysis` artifact older than `implement` |
| CHG-002 | change control | yes | API/schema impact flagged by design ⇒ `design_approval` decision payload acknowledges it |
| DEP-001 | dependencies | advisory | declared dependency licences ∈ allow-list |
| AUD-001 | audit | advisory | retention setting present |

`compliance_check` evaluates all; a mandatory `FAIL` raises a
`policy_exception` gate; without an approved, unexpired exception the run
safe-stops and release readiness is `NOT READY`.

## 8. Testing

Levels and markers: `unit`, `contract`, `integration`, `orchestration`,
`security`, `e2e`, `architecture`. Each test carries `@pytest.mark.req("FR-O08")`
markers; `scripts/traceability.py` builds the matrix from them. TDD order is
in `tasks.md`. Full suite target < 2 min; `verify` subprocess tests are tiny
workspace suites, not the repo suite.

## 9. Scenario Designs

| | SCN-A Greenfield | SCN-B Brownfield | SCN-C Ambiguous |
|---|---|---|---|
| Input | "Add per-link analytics summary endpoint (total, per-day)" | "Expired links return 410 instead of 404; analytics remain readable" | "Links should expire after a while and be reusable" |
| Quality check | clear → records reason no clarification needed | clear, scope=brownfield | HIGH ambiguity ×2 → clarification gate |
| Path | straight through, fan-out ×2 | impact_analysis branch, CHG-001 evaluated | WAITING_CLARIFICATION → decision → replan → resume |
| Faults (demo) | `verify` transient ×2 → retry succeeds | none (clean regression) | `security_review` permanent → fallback → exception gate |
| Gates | design_approval, release_readiness | design_approval, release_readiness | clarification, design_approval, policy_exception, release_readiness |
| Terminal | COMPLETED / READY | COMPLETED / READY | COMPLETED / READY WITH ACCEPTED LIMITATIONS |

Additional executed demonstrations (not scenarios): rejection → compensation;
gate timeout → safe-stop; restart mid-run → resume. Exported to
`docs/evidence/`.

## 10. Technology Decisions

See `research.md` and ADR-001..011. Summary: modular monolith; Python/FastAPI;
SQLite/SQLAlchemy; random base62 codes; hand-built DAG + tick scheduler with
thread pool; store-backed state with append-only events; gate-as-node approval
model; retry/fallback/safe-stop policies with rollback-vs-compensation rule;
graph-diff replanning; deterministic agents + run workspace; versioned policy
registry.

## 11. Traceability

Requirement → Scenario → Design (plan section) → ADR → Task (`tasks.md`) →
Code (path) → Test (marker) → Validation (command) → Documentation → Evidence
(`docs/evidence/`). Generated into `docs/traceability.md`.

## 12. Delivery Sequence and Timebox

| Slice | Content | Milestone |
|---|---|---|
| 1 Engineering baseline | pyproject, ruff/mypy/pytest config, CI-equivalent script, architecture test | Day 1 |
| 2 Walking skeleton | app factory, health, problem handler, SQLite db, CLI `serve` | Day 1 |
| 3 Core URL behaviour | validation, codes, create/resolve/expire/analytics/idempotency, rate limit, auth | Day 2 AM |
| 4 Orchestration state model | states, graph, store, events, context, engine tick + parallel | Day 2 |
| 5 Approval governance | gates, decisions, rejection, timeout → safe-stop | Day 2 |
| 6 Reliability controls | retry/backoff/timeout, fallback, workspace rollback, compensation, resume | Day 2 PM |
| 7 Observability | metrics incl. MTTR, lineage endpoint, evidence export | Day 3 AM |
| 8 Three scenarios | planner conditions, agents, replanning, scenario runs + evidence | Day 3 |
| 9 Release readiness | policy registry/evaluator, release check script, docs, traceability, reviewer guide, summary, tag | Day 3 PM |

**Must-have**: slices 1–9 as listed. **Deferred** (`BACKLOG.md`): LLM agent
adapter, DNS-resolving SSRF check, dedupe-by-URL index, Postgres store, async
analytics queue, OpenTelemetry export, Docker Compose.
**Stop conditions**: if slice 8 is not green by Day 3 midday, cut SCN-C fault
injection (keep clarification + replan) and the rejection demo moves to tests
only. **Minimum defensible outcome**: slices 1–6 + SCN-A/B/C executed once with
evidence + README/architecture/testing docs.
