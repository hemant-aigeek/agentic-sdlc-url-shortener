# Testing Approach, Limitations and Trade-offs

Everything in this document is checked by `./scripts/check.sh` (ruff, mypy
strict, pytest, OpenAPI drift, secret scan, licence allow-list) and recorded by
`python scripts/release_check.py` into `docs/evidence/release-check.json`.
Counts below are from the current suite; the traceability matrix in
[`traceability.md`](traceability.md) is generated from the same test markers
and fails the build if any requirement lacks a test.

## 1. Approach

### 1.1 Test-first, enforced by the commit history
Every behaviour group was built red → green: a `test(...)` commit with the
failing tests lands before the `feat(...)` commit that makes them pass
(`git log --oneline` shows the pairs, e.g. `test(orchestration): add failing
engine scheduler tests` → `feat(orchestration): establish workflow state and
dependency model with a parallel scheduler`). Where a test could not fail
meaningfully first (property tests over a pure function that already existed),
it was added in the same commit and is not described as TDD.

### 1.2 Requirement markers
Every test carries `@pytest.mark.req("FR-…", "NFR-…", "SCN-…", "ADR-…")`.
`scripts/traceability.py --check` fails when a requirement has no test or a
test cites an unknown id; `tests/architecture/test_traceability.py` runs that
check inside the suite so the matrix cannot drift.

### 1.3 Levels

| Level | Dir | Tests | What it proves | Representative tests |
|---|---|---|---|---|
| Unit — domain | `tests/unit` | 173 | URL validation incl. SSRF ranges (45, property-based with Hypothesis), short-code entropy and collision bounds (12), service rules (20), state-machine transition table (40), graph construction and cycle/ready/join semantics (16), policy evaluation (11), release rule (8), metrics incl. MTTR formula (7), deterministic agents (14) | `test_validation.py::test_rejects_loopback_private_linklocal_metadata`, `test_states.py` (every allowed/refused transition) |
| Contract | `tests/contract` | 28 | HTTP contract of both planes; the committed OpenAPI + JSON schemas equal what the app serves (drift test) | `test_links_api.py`, `test_workflow_api.py`, `test_openapi_drift.py` |
| Integration | `tests/integration` | 12 | SQLite repositories, health/readiness against a broken DB, redirect p95 benchmark (demo target, AS-02) | `test_link_repository.py`, `test_performance.py::test_redirect_p95_under_target_locally` |
| Orchestration | `tests/orchestration` | 49 | engine against a real SQLite store: dependency order, parallel fan-out (asserted by overlapping timestamps), join, conditional skip, lineage, event completeness; gates (no decision → no progress, attributable decisions, rejection compensates in reverse order, gate timeout → safe-stop, forged stage rows cannot move a run); reliability (bounded retry with backoff, permanent never retried, timeout counted as transient, fallback flagged, fallback failure → safe-stop, illegal transition → safe-stop, crash resume, suspend/resume with a fresh engine); workspace rollback; event-log reconstruction | `test_reliability.py`, `test_gates.py`, `test_store.py::test_stage_states_can_be_reconstructed_from_events_alone` |
| Security | `tests/security` | 18 | redirector abuse targets rejected, no tracebacks in problem responses, decisions require an actor, API key redacted from logs, bounded URL length | `test_security.py` |
| End-to-end | `tests/e2e` | 7 | the three scenarios plus rejection-rollback, restart-resume, policy-fail → NOT READY, design rejection with return-to, driven through the scenario runner against the real engine | `test_scenarios.py` |
| Architecture | `tests/architecture` | 3 | import-direction rule between planes (ADR-001); traceability has no orphans | `test_import_rules.py`, `test_traceability.py` |
| **Total** | | **290** | runs in ≈13 s locally (NFR-09 target < 2 min) | |

### 1.4 What is deliberately not mocked
The engine tests use the real SQLAlchemy workflow store on an in-memory SQLite
database (the restart/resume tests build a fresh `Engine` over the same store),
not a hand-written fake, so that event ordering, reconstruction and resume are tested against the
same persistence code the API uses. The only fakes are the
`Agent` implementations in `tests/orchestration/conftest.py` (scripted
success/failure/sleep) and the clock/sleep injected into the retry policy so
backoff is asserted without waiting.

### 1.5 Repository-level checks (release readiness)
`scripts/release_check.py` runs the quality gate, `pip-audit`, the licence
allow-list, the secret scan, and verifies the six evidence exports exist with
their expected terminal states. Its output is committed
(`docs/evidence/release-check.json`) and the decision vocabulary is the same
one the orchestrator uses (READY / READY WITH ACCEPTED LIMITATIONS / NOT READY).

## 2. What is demonstrated versus what is claimed

| Claim | Status | Evidence |
|---|---|---|
| Non-linear, stateful orchestration (fan-out, join, branch, replan) | Demonstrated | `test_engine_basic.py`, `tests/e2e`, `docs/evidence/*/graph.json` + `events.json` |
| Human gates cannot be bypassed | Demonstrated | `test_gates.py` (incl. forged-row test), `test_security.py::test_decisions_require_an_attributable_actor` |
| Bounded retry, timeout, fallback, safe-stop, resume | Demonstrated | `test_reliability.py`; `docs/evidence/{greenfield,ambiguous,resume,gate-timeout}` |
| Rollback vs. compensation | Demonstrated for workspace writes (true rollback) and for stage side effects (compensation in reverse order on rejection) | `test_workspace.py`, `test_gates.py::test_reject_*`, `docs/evidence/rejection` |
| Policy enforcement blocks release | Demonstrated | `test_policy.py`, `test_release.py`, `docs/evidence/policy-fail` |
| MTTR and latency measurement | Demonstrated on injected faults; values are demonstration data | `test_metrics.py`, `docs/evidence/*/metrics.json` |
| Brownfield impact analysis derived from the repository | Demonstrated (term/symbol scan) — not semantic | `docs/evidence/brownfield/artifacts.json` |
| Ambiguity detection | Demonstrated (rule-based) — not general NLU | `test_agents.py`, `docs/evidence/ambiguous` |
| Agents produce production code | **Not claimed.** Agents write red-test scaffolds and change plans into an isolated workspace; promotion is a human act (ADR-010) | `test_workspace.py` |
| Production performance / scale | **Not claimed.** p95 redirect < 50 ms is a local single-process measurement (AS-02) | `test_performance.py` |

## 3. Limitations

- **Deterministic agents.** No LLM is called. The `Agent` protocol is the
  extension point; the scenarios would need re-recording (and lose
  reproducibility) with a model behind it. This was a deliberate Gate 3
  decision (AMB-08).
- **Single process.** Parallelism is a thread pool inside one process; there
  is no lease/claim column, so two engine processes on one database would
  double-execute ready stages. The scaling path is documented in
  [`architecture.md`](architecture.md) §8, not built.
- **SQLite.** Adequate for the prototype; concurrent writers serialise on the
  file lock. The concurrency tests prove correctness (no duplicate codes, no
  lost events), not throughput.
- **SSRF check is literal.** Hostnames are checked against a block-list and
  literal IP ranges; DNS is not resolved (AMB-03), so a hostname that resolves
  to a private address is not caught. Recorded as a production recommendation.
- **Analytics are best-effort.** A crash between redirect and analytics write
  loses that event (AMB-05).
- **Rate limiting is per process** and keyed by API key only.
- **Gate timeout is wall-clock inside the engine loop**; a gate only times out
  when `run`/`resume` is invoked after the deadline, there is no background
  timer.
- **Scenario decisions in the committed evidence were scripted** and replayed
  under the operator's `--actor`. They are genuine decision records produced by
  `Engine.decide`, but they were not entered interactively; the walkthroughs
  give the interactive commands.
- **The scheduler is tick-based** (`run` executes ready batches until a gate
  or terminal state). There is no long-running daemon; `agentic-sdlc serve`
  advances runs on API calls.

## 4. Trade-offs made and why

| Trade-off | Chosen | Rejected | Reason |
|---|---|---|---|
| Hand-built engine vs. workflow framework | hand-built (≈3k lines in `orchestration/` including agents) | LangGraph, Temporal, Airflow | the orchestration *is* the deliverable; it must be readable and testable line by line (ADR-005) |
| Gates as graph nodes vs. callbacks | nodes | flags/callbacks on stages | a gate becomes a dependency; bypass is structurally impossible (ADR-007) |
| State rows + event log vs. events only | both | events only | fast reads for the API, reconstruction from events proven by test (ADR-006) |
| Determinism vs. realism of agents | determinism | LLM calls | reproducible evidence a reviewer can regenerate offline (ADR-010) |
| Depth in orchestration vs. breadth in the shortener | depth | vanity codes, dedupe index, dashboards | the assignment grades the control plane; the shortener is the subject (BACKLOG) |
| True rollback only where honest | workspace writes roll back; side effects compensate | "everything rolls back" | avoids claiming reversibility the system cannot guarantee (ADR-008) |
| Policies as versioned code vs. rules engine | code | YAML/OPA | testable in isolation, diff-reviewable, version pinned on every run (ADR-011) |

## 5. Running the suite

```bash
./scripts/check.sh                 # full gate
pytest -m "orchestration"          # one level
pytest tests/e2e -q                # the scenarios (≈3 s)
pytest -m "not slow"               # skip the benchmark
python scripts/release_check.py    # repository release readiness → docs/evidence/release-check.json
```
