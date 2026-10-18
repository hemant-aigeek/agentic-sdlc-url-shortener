# Feature Specification: Agentic Software Engineering System — URL Shortener

**Feature**: `001-agentic-url-shortener`
**Created**: 2026-10-15
**Status**: Approved — Gate 2 (2026-10-18); clarifications approved — Gate 3 (2026-10-18). See `docs/approvals/`.
**Input**: Interview assignment "Build an Agentic Software Engineering System — URL Shortener" (Schwab, Agentic-Proficient Software Engineer), sections 1–7.

This specification is implementation-independent. It does not choose a
language, framework, database, or agent framework; those are decided in the
plan and ADRs after Human Gate 3.

Identifier conventions used throughout the repository:

| Prefix | Meaning |
|---|---|
| `FR-Uxx` | Functional requirement — URL shortener (application plane) |
| `FR-Oxx` | Functional requirement — orchestration (control plane) |
| `FR-Gxx` | Functional requirement — governance, policy, approvals |
| `NFR-xx` | Non-functional requirement |
| `SCN-A/B/C` | Required demonstration scenarios |
| `AS-xx` | Assumption (proposed, requires human approval) |
| `AMB-xx` | Ambiguity requiring clarification |
| `EX-xx` | Explicit exclusion |

---

## 1. Business Objective

Demonstrate how a governed agentic execution system transforms a software
requirement into a reviewable engineering outcome across the full SDLC —
requirement understanding, ambiguity detection, decomposition, design,
controlled implementation, testing, documentation, security and risk
validation, release-readiness determination, and a final engineering summary —
while humans retain ownership of approvals and final quality.

The URL shortener exists so that the orchestration has something concrete to
build, change, and break. It is production-oriented in discipline, deliberately
small in scope.

---

## 2. User Journeys *(mandatory)*

### Journey 1 — API consumer shortens and follows a link (Priority: P1)

An API consumer submits a long URL and receives a short code; anyone who
follows the short link is redirected to the original URL, and the visit is
counted.

**Why this priority**: Without a working shortener there is nothing for the
orchestration to operate on and no brownfield surface to change.

**Independent test**: Create a link, follow it, read its analytics — all via
the HTTP API, with no orchestration involved.

**Acceptance scenarios**:
1. **Given** a valid `https` URL, **When** the consumer requests a short link,
   **Then** a unique short code is returned with the canonical short URL and
   expiry (if any).
2. **Given** an existing short code, **When** a client requests it, **Then** the
   client is redirected to the original URL and a redirect event is recorded.
3. **Given** an unknown short code, **When** a client requests it, **Then** the
   response is a not-found error, not a redirect.
4. **Given** a `javascript:` or `file:` URL, **When** the consumer requests a
   short link, **Then** the request is rejected with a validation error naming
   the field.

### Journey 2 — Software engineer submits a requirement to the orchestrator (P1)

A software engineer submits a requirement (greenfield, brownfield, or
ambiguous). The orchestration system ingests it, normalises it, decomposes it
into dependency-aware tasks, routes it through design, implementation,
testing, documentation, security, and release-readiness stages, and produces
an engineering summary — pausing at human gates.

**Why this priority**: This is the assessment's "critical differentiator".

**Independent test**: Submit a well-defined requirement and inspect the
resulting workflow state, event history, and artifacts without a human having
to intervene until the first mandatory gate.

**Acceptance scenarios**:
1. **Given** a well-defined requirement, **When** submitted, **Then** a workflow
   run is created with a correlation ID, an explicit dependency graph, and an
   initial state of `CREATED`, and the requirement-quality checks are recorded.
2. **Given** a running workflow with two independent stages ready, **When** the
   scheduler ticks, **Then** both stages execute (fan-out) and the dependent
   stage starts only after both complete (join).
3. **Given** a stage that fails transiently, **When** retried within bounds,
   **Then** the retry is recorded and the stage completes; **When** retries are
   exhausted, **Then** the stage's fallback runs or the workflow enters
   safe-stop, per the stage's policy.
4. **Given** a workflow paused at a human gate, **When** the process restarts,
   **Then** the workflow is resumable from the persisted state with full
   history intact.

### Journey 3 — Human reviewer approves, rejects, or clarifies (P1)

A human reviewer sees pending gates, inspects the context and decision lineage
that led there, and approves, rejects, or supplies a clarification. The
decision is recorded with actor, timestamp, and reason, and the workflow
transitions accordingly.

**Why this priority**: Controlled autonomy is a core requirement; without real
gates the system is an unsupervised chain.

**Independent test**: Drive a workflow to a gate, call the approval API with a
rejection, and verify the workflow does not progress and records the rejection.

**Acceptance scenarios**:
1. **Given** a workflow at an approval gate, **When** no decision is recorded,
   **Then** the workflow remains paused indefinitely (or until gate timeout →
   safe-stop); it never auto-advances.
2. **Given** a rejection, **When** recorded, **Then** downstream stages are
   not executed and the rejection reason is in the audit trail.
3. **Given** an ambiguity gate, **When** a clarification is supplied, **Then**
   the requirement is updated, downstream impact is computed, affected
   artifacts are invalidated, and the workflow resumes at the correct stage.

### Journey 4 — Release owner reads the readiness decision (P2)

A release owner inspects the release-readiness determination: which policies
were evaluated (and at which version), their outcomes, open exceptions, test
results, and the resulting decision.

**Acceptance scenarios**:
1. **Given** a failed mandatory policy, **When** release readiness is
   evaluated, **Then** the decision is `NOT READY` and names the failing policy.
2. **Given** an approved, unexpired exception with a compensating control,
   **When** evaluated, **Then** the decision may be `READY WITH ACCEPTED
   LIMITATIONS` and the exception is listed.

### Journey 5 — Assessment reviewer verifies the evidence (P2)

An assessment reviewer clones the repository, runs the setup, runs the tests,
exercises the API, replays the three scenarios, and locates — for any claim in
the documentation — the code, test, and executed evidence behind it.

**Acceptance scenarios**:
1. **Given** a clean clone and the README, **When** the reviewer follows the
   setup, **Then** the application starts and the full test suite passes.
2. **Given** a scenario walkthrough, **When** the reviewer runs the stated
   command, **Then** the output matches the committed evidence in structure
   (demonstration data is labelled as such).

---

## 3. Functional Requirements — URL Shortener (application plane)

| ID | Requirement | Negative / edge behaviour |
|---|---|---|
| FR-U01 | Create a short link from a target URL. Response includes short code, short URL, target URL, created-at, expires-at (nullable). | Missing/blank URL → validation error. |
| FR-U02 | Validate target URLs: syntactically valid absolute URL; scheme in the allow-list (`http`, `https`); host present; maximum length enforced. | `javascript:`, `data:`, `file:`, `ftp:`, relative URLs, URLs > max length → rejected with field-level error. |
| FR-U03 | Reject target URLs whose host resolves to or literally is a loopback, link-local, private (RFC 1918 / ULA), or cloud-metadata address. | `http://127.0.0.1/`, `http://169.254.169.254/`, `http://10.0.0.5/` → rejected. See AMB-03 for DNS-resolution scope. |
| FR-U04 | Generate short codes that are unique, URL-safe, and not predictable from the target URL or sequence. | Collision on generation → regenerate, bounded attempts; exhaustion → persistence error, no partial record. |
| FR-U05 | Resolve a short code to its target and redirect the client. | Unknown code → 404 problem response. |
| FR-U06 | Support optional expiration on a link. Expired links do not redirect. | Expired code → 410 Gone, not 404, so the client can distinguish. Expiry in the past at creation → validation error. |
| FR-U07 | Record a redirect event per successful resolution (timestamp, short code, optional referrer, coarse user-agent class). | Analytics write failure MUST NOT fail the redirect (see AMB-05 for consistency choice). |
| FR-U08 | Expose per-link analytics: total redirects, first/last redirect time, redirects grouped by day. | Unknown code → 404. Expired link's analytics remain readable. |
| FR-U09 | Support idempotent creation via a client-supplied idempotency key: same key + same payload → same short code; same key + different payload → conflict. | Missing key → non-idempotent create (new code each time). |
| FR-U10 | Handle concurrent creation and redirect requests without duplicate short codes or lost analytics events. | Concurrency test with N parallel creates → N distinct codes. |
| FR-U11 | Degrade predictably on persistence failure: creation returns a service-unavailable problem response; redirect returns service-unavailable; no partial writes. | Simulated store failure in tests. |
| FR-U12 | Expose liveness (`/health/live`) and readiness (`/health/ready`) endpoints; readiness checks the persistence dependency. | Store unavailable → readiness fails, liveness succeeds. |
| FR-U13 | All error responses use one structured problem format (type, title, status, detail, instance/correlation ID, field errors where applicable). | — |

## 4. Functional Requirements — Orchestration (control plane)

| ID | Requirement |
|---|---|
| FR-O01 | Create a workflow run from a requirement submission; assign a correlation (run) ID; persist the run. |
| FR-O02 | Represent the run as an explicit dependency graph: named stages, directed dependencies, entry and exit gates per stage. The graph is inspectable via API. |
| FR-O03 | Execute stages according to the graph: a stage becomes ready only when all dependencies have exited successfully (or via an accepted fallback); independent ready stages execute in parallel; a join waits for all its inputs. |
| FR-O04 | Support conditional branches whose path is chosen from a prior stage's output (e.g. requirement-quality check → clarification path or direct decomposition path). |
| FR-O05 | Stage lifecycle states: `PENDING → READY → RUNNING → {SUCCEEDED, FAILED, RETRYING, FALLBACK, COMPENSATING, COMPENSATED, SKIPPED, INVALIDATED}`. Run states: `CREATED, RUNNING, WAITING_APPROVAL, WAITING_CLARIFICATION, REPLANNING, SUSPENDED, SAFE_STOPPED, COMPLETED, FAILED, REJECTED`. Transitions outside the defined set are refused. |
| FR-O06 | Persist workflow state, stage state, stage inputs/outputs, context, decisions, assumptions, approvals, artifact versions, and an append-only event log such that a run can be reconstructed and resumed after process restart. |
| FR-O07 | Preserve decision lineage: every artifact produced by a stage records which upstream artifacts, decisions, and policy version it was derived from. |
| FR-O08 | Classify stage failures as transient or permanent. Retry transient failures with bounded attempts, backoff, and per-attempt timeout; never retry permanent failures. Record each attempt. |
| FR-O09 | Enforce a per-stage timeout; a timed-out attempt counts as a transient failure unless classified otherwise. |
| FR-O10 | Support per-stage fallback: an alternative action executed when retries are exhausted, whose use is recorded and visible in the result. |
| FR-O11 | Support compensation: when a stage has produced side effects and a downstream failure or rejection requires undoing them, run the stage's compensating action in reverse dependency order. Distinguish rollback (restore prior state) from compensation (counteracting action). |
| FR-O12 | Enter `SAFE_STOPPED` when continuation is unsafe: retries exhausted without fallback, gate timeout, unresolved mandatory policy failure, invalid state transition detected, or explicit operator stop. Safe-stop is terminal for that run, records the reason, and leaves state consistent. |
| FR-O13 | Resume a run from persisted state after interruption (process restart or suspension) without re-executing succeeded stages, and record the resumption. |
| FR-O14 | Dynamic replanning: when an upstream output changes (clarification, rejected design, changed requirement), compute the set of downstream stages whose inputs are invalidated, mark them `INVALIDATED`, regenerate the affected part of the graph, record a replanning event with before/after graph, and resume from the first invalidated stage — without re-running unaffected stages and without bypassing gates. |
| FR-O15 | Ingest a requirement and normalise it into a structured form: title, intent, scope classification (greenfield / brownfield / ambiguous), functional statements, constraints, acceptance criteria, and detected ambiguities with severity. |
| FR-O16 | Decompose a normalised requirement into tasks with IDs, dependencies, parallelisation flags, affected components, and acceptance criteria. |
| FR-O17 | For brownfield requirements, perform impact analysis before any change: impacted modules, interfaces, data flows, tests, documentation, regression risks, and rollout/rollback considerations, derived from the actual repository. |
| FR-O18 | Produce stage outputs for design, implementation plan, test plan, documentation, security review, and release readiness as inspectable artifacts attached to the run. |
| FR-O19 | Expose metrics per run and aggregated: success rate, failure rate, retry count/frequency, fallback count, compensation/rollback count, safe-stop count, recovery durations, MTTR (recovered events only; unrecovered reported separately), and end-to-end latency. Measurements are labelled demonstration data. |
| FR-O20 | Expose the audit trail per run: ordered events with actor type (agent / human / system), action, timestamp, affected stage or artifact, result, reason, and policy version where applicable. |

## 5. Functional Requirements — Governance (approvals and policy)

| ID | Requirement |
|---|---|
| FR-G01 | Mandatory human approval gates exist at: unresolved ambiguity, architecture/design approval, security-sensitive action, destructive or irreversible action, constitutional/policy exception, material risk acceptance, release readiness. Gates cannot be disabled by configuration. |
| FR-G02 | A gate exposes: what is being approved, the artifacts and decisions leading to it, the policy outcomes, and the options (approve / reject / clarify). |
| FR-G03 | A recorded decision includes actor identity, decision, timestamp, reason, and the artifact version it applied to. |
| FR-G04 | Absence of a decision never advances the workflow. A gate may have a timeout; on timeout the run enters `SAFE_STOPPED` with reason `GATE_TIMEOUT`. |
| FR-G05 | Rejection stops downstream execution, triggers compensation where side effects exist, and ends the run in `REJECTED` (or returns to an upstream stage if the rejection names one). |
| FR-G06 | Policies are versioned. Every run records the policy version evaluated. Each applicable policy check yields `PASS`, `FAIL`, `EXCEPTION-REQUESTED`, or `NOT-APPLICABLE`. |
| FR-G07 | Policy domains in scope: security (URL validation rules, secret exposure), compliance (audit completeness, approval presence), change control (impact analysis before brownfield change; versioned API/schema change approval), dependency/licensing (allow-listed licences). |
| FR-G08 | A `FAIL` on a mandatory policy blocks downstream progression and release readiness. |
| FR-G09 | Exceptions require explicit human approval and record policy, reason, scope, approving authority, compensating control, approval timestamp, and expiry/review condition. Expired or unapproved exceptions behave as `FAIL`. |
| FR-G10 | Release-readiness determination produces exactly one of `READY`, `READY WITH ACCEPTED LIMITATIONS`, `NOT READY`, with the evidence it was based on. |

---

## 6. Required Scenarios

### SCN-A — Greenfield (well-defined requirement)
**Input**: a complete, consistent, testable requirement for a *new* capability
of the URL shortener (candidate, to be fixed in the plan: *"Add a per-link
analytics summary endpoint returning total redirects and redirects per day."*).
**Required behaviour**: requirement-quality checks pass; the workflow records
*why* clarification is not required; it proceeds Requirement → Decomposition →
Design → Implementation → Testing → Documentation → Validation → Release
Readiness without an artificial clarification gate; architecture approval and
release-readiness gates still apply. If ambiguity emerges mid-run, only the
affected path suspends.
**Evidence**: quality-check record, decomposition, API/schema impact, acceptance
criteria, stage history, approvals, terminal state.

### SCN-B — Brownfield (change to existing behaviour)
**Input**: an enhancement or defect fix against the existing shortener
(candidate: *"Expired links must return 410 Gone instead of 404, and analytics
for expired links must remain readable."*).
**Required behaviour**: impact analysis stage runs *before* any change and
identifies impacted modules, interfaces, data flows, tests, documentation,
regression risks, and rollback considerations; change-control policy requires
the impact analysis to exist; implementation proceeds test-first; regression
suite is executed.
**Evidence**: impact analysis artifact, policy outcome, diff summary, test
results before/after, approval record.

### SCN-C — Ambiguous requirement
**Input**: an incomplete or conflicting requirement (candidate: *"Links should
expire after a while and be reusable."* — "a while" is undefined; "reusable"
conflicts with short-code uniqueness).
**Required behaviour**: ambiguity detected with severity; implementation path
blocked; run enters `WAITING_CLARIFICATION`; clarification request lists
options and their engineering impact; a human decision is recorded; downstream
impact computed; invalidated artifacts regenerated (replanning event); run
resumes at the correct stage; terminal outcome recorded.
**Evidence**: ambiguity record, blocked-state proof, clarification request,
human decision, replanning event with before/after graph, resumed history.

The three scenarios MUST be materially different in path shape (A: straight
through with parallel fan-out; B: impact-analysis branch + change-control
policy; C: suspension + replanning).

---

## 7. Non-Functional Requirements

Where the assignment gives no numeric target, the target below is a **proposed
validation target (assumption)** and is marked `AS-` for approval at Gate 3.

| ID | Area | Requirement / proposed target | Verification |
|---|---|---|---|
| NFR-01 | Security | Scheme allow-list, private/loopback/metadata rejection, no secrets in logs/events, structured errors without stack traces. | Security tests; log inspection test. |
| NFR-02 | Reliability | All orchestration retries bounded (proposed default: 3 attempts, exponential backoff, per-attempt timeout) — AS-01. | Retry/timeout tests. |
| NFR-03 | Recoverability | A run interrupted at any non-terminal state resumes without re-executing succeeded stages. | Resume tests with simulated restart. |
| NFR-04 | Observability | Every log line and event carries the run correlation ID; a run can be reconstructed from the event log alone. | Reconstruction test. |
| NFR-05 | Auditability | Audit events are append-only and ordered; no update/delete path exists in the API. | Persistence tests. |
| NFR-06 | Performance | Redirect p95 < 50 ms locally with the reference store (demonstration measurement) — AS-02. | Local benchmark, labelled demo data. |
| NFR-07 | Scalability | Persistence and short-code generation are behind interfaces so the store can be swapped without touching domain or API code; documented scaling path. | Architecture review; interface tests. |
| NFR-08 | Maintainability | Modules: domain, api, persistence, orchestration, policy, telemetry, config — no cyclic imports; type-checked; linted. | Import-graph check; CI-equivalent script. |
| NFR-09 | Testability | Every FR maps to at least one automated test; the suite runs locally in < 2 min — AS-03. | Traceability matrix; timed run. |
| NFR-10 | Change safety | Brownfield changes are blocked by policy until impact analysis exists; versioned API/schema changes require approval. | Policy tests; SCN-B. |
| NFR-11 | Controlled autonomy | Agents cannot transition past a gate; mandatory gates cannot be configured off. | Governance tests. |
| NFR-12 | Local runnability | Clean clone → running app + green suite with documented commands, no external services. | Clean-clone verification (recorded). |

---

## 8. Key Entities (implementation-independent)

- **ShortLink**: short code, target URL, created-at, expires-at, idempotency key (optional), status (active/expired).
- **RedirectEvent**: short code, occurred-at, referrer (optional), user-agent class.
- **WorkflowRun**: run ID, requirement, scope classification, state, policy version, created/updated, terminal reason.
- **Stage**: run ID, stage name, state, attempt count, inputs/outputs reference, started/ended, failure classification, fallback used.
- **Dependency**: run ID, from-stage, to-stage, kind (hard / conditional).
- **Decision**: run ID, gate, actor, decision, reason, timestamp, artifact version.
- **Artifact**: run ID, stage, kind, version, content, derived-from (lineage).
- **PolicyEvaluation**: run ID, policy ID, policy version, outcome, detail.
- **PolicyException**: policy ID, scope, reason, approver, compensating control, approved-at, expires-at.
- **AuditEvent**: run ID, sequence, actor type, action, target, result, reason, timestamp.
- **ReplanEvent**: run ID, trigger, invalidated stages, graph before, graph after, timestamp.

---

## 9. Ambiguities — RESOLVED at Gate 3 (2026-10-18)

All items below were decided by the candidate; the "Proposed default" column
is the accepted decision. Decision rationale is in
`docs/approvals/GATE-3-clarifications.md`.

| ID | Question | Options and impact | Decision (accepted) |
|---|---|---|---|
| AMB-01 | Duplicate target URL: should the same URL always map to the same short code? | (a) Always new code — simplest, supports per-campaign links. (b) Dedupe per URL — needs lookup index, changes idempotency semantics. | (a), with idempotency key for explicit dedupe (FR-U09). |
| AMB-02 | Short code format and length. | (a) 7-char base62 random — ~3.5 trillion space, low collision. (b) Sequential encoded ID — predictable. (c) Hash-based — deterministic, enables dedupe. | (a). |
| AMB-03 | Private-address rejection: literal IP check only, or DNS-resolve hostnames at creation? | Literal-only: no network call, misses `evil.example` → 127.0.0.1. Resolve: more secure, adds latency and a network dependency in tests. | Literal + documented hostname block-list; DNS resolution recorded as a production recommendation. |
| AMB-04 | Expiration precision and default. | No default expiry vs. default N days. Second-level precision assumed. | No default expiry; optional `expires_at`. |
| AMB-05 | Analytics consistency: redirect-path write must never block the redirect. | (a) Synchronous write, same transaction — consistent, slower, redirect fails if analytics fails. (b) Best-effort in-process async — fast, may lose events on crash. | (b) with explicit "eventually consistent, loss on crash" limitation. |
| AMB-06 | Authentication for create/analytics/approval endpoints. | None (assume trusted network) vs. static API key vs. real identity. Approvals need an actor identity regardless. | Static API key header for mutating and approval endpoints, actor name carried in a header; documented as an assumption. |
| AMB-07 | Rate limiting: implement or document? | Implement simple token bucket vs. document as deployment concern. | Implement a minimal in-process limiter on creation; document production placement. |
| AMB-08 | Who are the "agents"? Real LLM calls or deterministic stage executors? | LLM: realistic but non-deterministic, needs keys, untestable offline. Deterministic executors with an LLM-pluggable interface: reproducible, testable, honest about what is demonstrated. | Deterministic executors behind an `Agent` interface; LLM adapter as backlog. |
| AMB-09 | Gate timeout duration and behaviour. | Minutes vs. hours vs. none. | Configurable per gate; default none for interactive demo, explicit timeout in tests → safe-stop. |
| AMB-10 | Rollback vs. compensation for implementation stages that write files. | Rollback via VCS vs. compensation by recorded inverse action. | Stages record inverse actions; rollback where the change is a reversible store write, compensation otherwise. |
| AMB-11 | Audit retention. | Forever (demo) vs. N days. | Retain for the life of the local store; retention policy documented. |
| AMB-12 | Deployment target. | Local only vs. container. | Local process + optional Dockerfile; no cloud. |

## 10. Assumptions (APPROVED at Gate 3 as validation targets)

- AS-01 Default retry policy: 3 attempts, exponential backoff starting 100 ms, per-attempt timeout 5 s (tests use shorter values).
- AS-02 Performance targets are demonstration measurements on a developer machine.
- AS-03 Full suite under 2 minutes locally.
- AS-04 A single-process, single-node deployment is sufficient for the assessment; horizontal scaling is a documented path, not an implemented one.
- AS-05 The reviewer runs on a machine with the chosen language runtime installed; no other services are required.

## 11. Exclusions

- EX-01 User accounts, multi-tenancy, custom aliases/vanity codes.
- EX-02 Distributed workers, message brokers, external workflow engines.
- EX-03 Real LLM-backed agents (interface provided; adapter deferred).
- EX-04 Production deployment, TLS termination, CDN, geo-analytics.
- EX-05 UI beyond API documentation.

## 12. Success Criteria

| ID | Criterion |
|---|---|
| SC-01 | A reviewer can run the app and the full suite from a clean clone using only README commands. |
| SC-02 | All three scenarios execute end-to-end through the real orchestrator via a documented command, producing committed evidence. |
| SC-03 | Every FR/NFR maps to at least one test or demonstration in the traceability matrix; no orphan requirements, tasks, or tests. |
| SC-04 | At least one real parallel fan-out/join, one retry→fallback, one compensation, one safe-stop, one resume, and one replanning event are visible in executed evidence (not only in docs). |
| SC-05 | No workflow in the evidence advances past a human gate without a recorded decision. |
| SC-06 | Release-readiness evidence shows a failed mandatory policy producing `NOT READY`. |
| SC-07 | The final engineering summary cites repository paths and commands for every material claim. |

---

## Gate 2 Review Checklist (for the human candidate)

Reject this specification if it: chooses technologies prematurely · silently
resolves an ambiguity · lacks negative behaviour · omits a required scenario ·
presents orchestration as a linear chain · lacks human approval · lacks
recovery or safe-stop · cannot be tested · cannot be traced.
