# Reviewer Guide

How to locate and verify every claim this repository makes, in under an hour.
Each row gives the path, the command where one applies, what you should
observe, and the requirement or scenario id it serves. Nothing here relies on
a statement in a README; every item is a file you can open or a command you
can run.

Conventions: `<run_id>` is printed by any `scenario run` / `workflow start`
command. All commands assume the setup in §2 has been done and the virtualenv
is active.

## 1. Objective

| Where | What |
|---|---|
| `specs/001-agentic-url-shortener/spec.md` §1–2 | business objective and the five user journeys |
| `.specify/memory/constitution.md` | the eleven engineering principles the work was held to |
| `docs/final-engineering-summary.md` | the outcome, in the 21-section schema |

## 2. Run the application and the tests (NFR-12, SC-01)

```bash
git clone https://github.com/hemant-aigeek/agentic-sdlc-url-shortener.git
cd agentic-sdlc-url-shortener
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
./scripts/check.sh                                      # expected: "ALL CHECKS PASSED", 290 tests
agentic-sdlc serve                                      # http://127.0.0.1:8000/docs
```

Clean-clone verification as executed by the candidate: `docs/evidence/clean-clone.md`.

## 3. Exercise the URL shortener (FR-U01 … FR-U13)

```bash
export K='X-API-Key: dev-key'
curl -s -X POST localhost:8000/api/v1/links -H "$K" -H 'content-type: application/json' \
     -d '{"target_url":"https://example.com/a"}'                       # 201, code, short_url
curl -i localhost:8000/<code>                                           # 307 Location: https://example.com/a
curl -s localhost:8000/api/v1/links/<code>/analytics -H "$K"            # total_redirects: 1, redirects_by_day
curl -s -X POST localhost:8000/api/v1/links -H "$K" -H 'content-type: application/json' \
     -d '{"target_url":"http://169.254.169.254/latest/meta-data"}'     # 422 problem+json, FR-U03
curl -s -X POST localhost:8000/api/v1/links -H "$K" -H 'content-type: application/json' \
     -d '{"target_url":"https://example.com/x","expires_at":"2020-01-01T00:00:00Z"}'  # 422, past expiry
curl -i localhost:8000/nosuchcode                                       # 404 problem+json
curl -s localhost:8000/health/ready                                     # {"status":"ok","checks":{"database":"ok"}}
```

Expired → `410 Gone` (FR-U06) and idempotency-key behaviour (FR-U09) are
exercised in `tests/contract/test_links_api.py`; the contract itself is
`specs/001-agentic-url-shortener/contracts/openapi.yaml` and is drift-checked
by `tests/contract/test_openapi_drift.py`.

## 4. Orchestration — start, inspect, approve (FR-O01 … O07, FR-G01 … G05)

```bash
agentic-sdlc workflow start "Add a per-link analytics summary endpoint returning total redirects and redirects per day. Unknown codes return 404." --scope greenfield
#   → prints <run_id>; run advances to the first human gate
agentic-sdlc workflow inspect <run_id>        # state WAITING_APPROVAL; stage table; open gate design_approval
agentic-sdlc workflow gates <run_id>          # what is being approved + the artifacts and decisions that led there
agentic-sdlc workflow run <run_id>            # expected: nothing happens — no decision, no progress (FR-G04)
agentic-sdlc workflow decide <run_id> design_approval approve --actor you --reason "ok" --payload '{"api_change_acknowledged": true}'
agentic-sdlc workflow inspect <run_id>        # now WAITING_APPROVAL at release_readiness; implement/test_plan/docs_draft ran in parallel
agentic-sdlc workflow decide <run_id> release_readiness approve --actor you --reason "ok"
agentic-sdlc workflow events <run_id>         # ordered audit trail: actor type, action, stage, result, reason (FR-O20)
agentic-sdlc workflow metrics <run_id>        # success rate, retries, MTTR, latency (FR-O19)
agentic-sdlc workflow release <run_id>        # READY (FR-G10)
```

The same operations over HTTP: `POST /api/v1/workflows`,
`GET /api/v1/workflows/{run_id}`, `/graph`, `/gates`, `/events`, `/lineage`,
`/metrics`, `POST /api/v1/workflows/{run_id}/gates/{gate}/decision` (needs
`X-API-Key` and `X-Actor`). Interactive docs at `/docs`.

## 5. Demonstrate each reliability and governance control

Every demonstration is a scenario you can replay; the committed export of the
candidate's own run is beside it.

| Control | Command | Expected observation | Committed evidence | Ids |
|---|---|---|---|---|
| Parallel fan-out + join | `agentic-sdlc scenario run greenfield --actor you` | `implement`, `test_plan`, `docs_draft` start before any of them finishes; `verify` starts after all three | `docs/evidence/greenfield/events.json` seq 18–27 | FR-O03 |
| Bounded retry with backoff + MTTR | same run (the scenario enables 2 transient faults on `verify`) | `failure_detected TRANSIENT` → `retry_scheduled` ×2 → success on attempt 3; `metrics.json` MTTR from timestamps | `greenfield/metrics.json` | FR-O08, FR-O19 |
| Conditional branch / no artificial clarification | same run | `stage_skipped clarification — condition … is false` with the quality-check reason | `greenfield/artifacts.json` kind `quality_check` | FR-O04, SCN-A |
| Brownfield impact analysis before change | `agentic-sdlc scenario run brownfield --actor you` | `impact_analysis` succeeds before `decompose`; `CHG-001 PASS` | `docs/evidence/brownfield/` | FR-O17, SCN-B |
| Ambiguity → blocked → clarification → replan → resume | `agentic-sdlc scenario run ambiguous --actor you --no-decide` then the printed `decide` command | run is `WAITING_CLARIFICATION`; after `clarify`, `replan v2` event, 14 stages invalidated, resumes at `requirement_revision` | `docs/evidence/ambiguous/replans.json` | FR-O14, SCN-C |
| Fallback on permanent failure + policy exception | same run with `--decide` | `security_review` → `FALLBACK`; `SEC-003 EXCEPTION-REQUESTED`; `policy_exception` gate; exception record with compensating control and expiry | `ambiguous/policy.json` | FR-O10, FR-G09 |
| Rejection → compensation / rollback | `agentic-sdlc scenario run rejection --actor you` | `release_readiness` rejected → `implement` becomes `COMPENSATED`, workspace change set removed, run `REJECTED` | `docs/evidence/rejection/` | FR-O11, FR-G05 |
| Safe-stop on failed mandatory policy → NOT READY | `agentic-sdlc scenario run policy-fail --actor you` | run `SAFE_STOPPED`, reason `POLICY_BLOCKED: … SEC-002`; `release` prints `NOT READY` | `docs/evidence/policy-fail/` | FR-O12, FR-G08, SC-06 |
| Resume after interruption | `agentic-sdlc scenario run resume --actor you` | first engine runs one batch and stops (`SUSPENDED`); a fresh engine resumes; succeeded stages are not re-executed; `run_resumed` event | `docs/evidence/resume/` | FR-O13 |
| Gate timeout → safe-stop | `agentic-sdlc scenario run gate-timeout --actor you` | no decision within 1 s → `SAFE_STOPPED`, reason `GATE_TIMEOUT` | `docs/evidence/gate-timeout/` | FR-G04 |
| Operator safe-stop | `agentic-sdlc workflow stop <run_id> --actor you --reason "…"` on any waiting run | `SAFE_STOPPED` with the reason; no further transitions accepted | `tests/orchestration/test_gates.py::test_operator_stop_is_recorded_safe_stop` | FR-O12 |
| Dynamic replan from an upstream change | `agentic-sdlc workflow replan <run_id> --trigger "requirement changed" --data '{"requirement": "…"}'` on a waiting run | new graph version, invalidated downstream stages, gates regenerated | `tests/e2e/test_scenarios.py::test_ambiguous_…` | FR-O14 |
| Decision lineage | `curl localhost:8000/api/v1/workflows/<run_id>/lineage -H "$K"` | each artifact lists `derived_from` artifacts, decisions and policy version | `docs/evidence/*/artifacts.json` | FR-O07 |
| Event-log reconstruction | `pytest tests/orchestration/test_store.py -k reconstructed` | stage states rebuilt from events equal the stored rows | — | NFR-04 |

Re-export any run yourself: `agentic-sdlc workflow export-evidence <run_id> --out /tmp/evidence`.

## 6. Three scenarios

| Scenario | Walkthrough | Evidence | Test |
|---|---|---|---|
| SCN-A greenfield | `docs/scenarios/greenfield.md` | `docs/evidence/greenfield/` | `tests/e2e/test_scenarios.py::test_greenfield_proceeds_without_clarification_with_parallel_fanout_and_retry` |
| SCN-B brownfield | `docs/scenarios/brownfield.md` | `docs/evidence/brownfield/` | `::test_brownfield_runs_impact_analysis_before_any_change` |
| SCN-C ambiguous | `docs/scenarios/ambiguous.md` | `docs/evidence/ambiguous/` | `::test_ambiguous_requirement_blocks_clarifies_replans_and_accepts_exception` |

## 7. Architecture, decisions, traceability

| Item | Where |
|---|---|
| Architecture overview (planes, control flow, state machines, key decisions) | `docs/architecture.md` |
| ADRs 001–011 with options, consequences, reversibility | `docs/adr/` |
| Human gate records (constitution, spec, clarifications, architecture, release) | `docs/approvals/` |
| Plan, research, data model, quickstart, tasks | `specs/001-agentic-url-shortener/` |
| Requirement → task → test → evidence matrix (generated; build fails on orphans) | `docs/traceability.md`, `python scripts/traceability.py --check` |
| Import-direction rule between planes | `tests/architecture/test_import_rules.py` |

## 8. API contracts and schemas (plan §2)

| Item | Where / command |
|---|---|
| OpenAPI 3.1 contract, version `1.0.0` | `specs/001-agentic-url-shortener/contracts/openapi.yaml` |
| JSON schemas (requests, responses, problem, workflow views) | `specs/001-agentic-url-shortener/contracts/schemas/*.json` |
| Drift check | `python scripts/export_contracts.py --check` (also in `check.sh`) |
| Compatibility / migration rule | `specs/001-agentic-url-shortener/plan.md` §2 (additive changes within a major; breaking → new major path); CHG-002 requires acknowledgement at design approval |
| Contract tests | `tests/contract/` |

## 9. Compliance, change control, exceptions

| Item | Where / command |
|---|---|
| Policy registry (ids, versions, mandatory flag, domains) | `agentic-sdlc workflow policies` or `GET /api/v1/policies`; source `src/agentic_sdlc/policy/registry.py` |
| Policy version recorded per run | `docs/evidence/*/run.json` → `policy_version` |
| Outcomes PASS / FAIL / EXCEPTION-REQUESTED / NOT-APPLICABLE | `docs/evidence/*/policy.json` |
| Approved exception with scope, approver, compensating control, expiry | `docs/evidence/ambiguous/policy.json` → `exceptions` |
| Failed mandatory policy blocks release | `docs/evidence/policy-fail/`; `tests/unit/test_release.py` |
| Change control: impact analysis required for brownfield | CHG-001 in `brownfield/policy.json` (PASS) vs `greenfield/policy.json` (NOT-APPLICABLE) |

## 10. Reliability measurements and MTTR

| Item | Where |
|---|---|
| Definition and formula | `docs/evidence/<scenario>/README.md` "Metrics" section; `src/agentic_sdlc/orchestration/metrics.py` |
| Inputs: failure-detected / recovery-start / recovery-complete timestamps | `events.json` kinds `failure_detected`, `recovery_started`, `recovery_completed` |
| Recovered population vs. unrecovered (excluded from denominator) | `metrics.json` → `recovery.recovered_failures`, `recovery.unrecovered` |
| Aggregate across all runs | `agentic-sdlc workflow metrics` (no run id) or `GET /api/v1/metrics` |
| Demonstration-data labelling | banner at the top of every evidence README; `metrics.json` → `measurement_type` / `measurement_note` |

## 11. Security controls

| Control | Where |
|---|---|
| Scheme allow-list, length bound, credentials-in-URL rejection | `src/agentic_sdlc/domain/validation.py`, `tests/unit/test_validation.py` |
| Loopback / link-local / private / ULA / metadata rejection + hostname block-list | same; `tests/security/test_security.py::test_redirector_abuse_targets_are_rejected` |
| No secrets in logs or events | `tests/security/test_security.py::test_api_key_is_redacted_from_structured_logs`; `scripts/secret_scan.py` |
| API key on mutating endpoints; `X-Actor` on decisions | `src/agentic_sdlc/api/auth.py`; `test_decisions_require_an_attributable_actor` |
| Rate limiting on creation | `src/agentic_sdlc/api/ratelimit.py`; 429 contract test |
| Dependency audit and licence allow-list | `docs/evidence/release-check.json`; `scripts/license_check.py` |
| Threat notes and residual risks | `docs/architecture.md` §6 |

## 12. Known limitations and the final summary

| Item | Where |
|---|---|
| Limitations and trade-offs | `docs/testing.md` §2–4; `BACKLOG.md` |
| Independent review of the submission | `docs/reviews/final-assessment.md` |
| Final engineering summary (21 sections) | `docs/final-engineering-summary.md` |
| Release decision | `docs/approvals/GATE-5-release-readiness.md`; tag `assessment-submission-v1.0` |
