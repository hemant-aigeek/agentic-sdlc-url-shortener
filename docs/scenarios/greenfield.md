# Scenario A — Greenfield: a well-defined requirement goes straight through

**Requirement id**: SCN-A · **Evidence**: [`docs/evidence/greenfield/`](../evidence/greenfield/README.md) (run `01a1502e01bb9f20673485e06a`) · **Terminal**: `COMPLETED` / release `READY`

## 1. Input

> Add a per-link analytics summary endpoint `GET /api/v1/links/{code}/analytics/summary`
> returning total redirects, first and last redirect time, and redirects per day.
> Unknown codes return 404. Expired links keep their analytics readable.

Submitted with `scope=greenfield`. One demonstration fault is enabled for this
run: the `verify` stage fails transiently on its first two attempts
(`AGENTIC_DEMO_FAULT_VERIFY_TRANSIENT_FAILURES=2`) so that bounded retry and
MTTR measurement are exercised on a real path, not a unit test.

## 2. What the assignment asks this scenario to prove

A well-defined requirement must proceed **without an artificial clarification
gate**, and the workflow must record *why* clarification was not required —
not merely skip it. Architecture approval and release readiness still gate.

## 3. Path shape

```
ingest → quality_check ─(clarification_required = false → SKIPPED)→ decompose → design
       → [design_approval · HUMAN] → { implement ‖ test_plan ‖ docs_draft } → verify (×3)
       → security_review → compliance_check ─(no blocking policy → SKIPPED)→
         [release_readiness · HUMAN] → summary
```

| Property under assessment | Where to look in the evidence |
|---|---|
| Requirement-quality checks recorded | `artifacts.json` → kind `quality_check`: completeness, consistency, testability, boundaries all `passed`; `reason_no_clarification` field |
| Clarification gate skipped *with a reason* | `events.json` seq 9: `stage_skipped clarification — condition 'quality_check.clarification_required' is false` |
| Decomposition with dependencies and parallel flags | `artifacts.json` → kind `decomposition` (tasks with `depends_on`, `parallel`, `tdd` red/green) |
| API/schema impact acknowledged | design-approval gate reason cites CHG-002; `policy.json` → `CHG-002 PASS` |
| Parallel fan-out and join | seq 18–26: three `stage_ready`/`stage_started` for `docs_draft`, `implement`, `test_plan` tagged `parallel_group=after:design_approval`; seq 27 `verify` becomes ready only after all three succeed |
| Bounded retry on a transient failure | seq 29–37: `failure_detected TRANSIENT` → `retry_scheduled` (attempt 1, 2) → `stage_succeeded` on attempt 3 → `recovery_completed RECOVERED` |
| MTTR captured from timestamps | `metrics.json`: one recovered failure, recovery duration 5.22 s, zero unrecovered; formula stated in `README.md` |
| Human gates actually waited | seq 16/17 and 45/46: `gate_opened WAITING` precedes every `decision_recorded`; no stage downstream of a gate starts before the decision |
| Policy version recorded | `run.json` → `policy_version: 1.0.0`; every row in `policy.json` carries it |
| Release-readiness decision | `scenario.json` → `outcome.release_decision: READY`; 8 × `PASS`, 1 × `NOT-APPLICABLE` (CHG-001, greenfield) |
| Terminal outcome | seq 50 `run_completed COMPLETED` |

## 4. Re-running it

```bash
agentic-sdlc scenario run greenfield --actor <your-name> --export /tmp/evidence
# or, step by step with real human decisions:
agentic-sdlc scenario run greenfield --actor <your-name> --no-decide   # stops at design_approval
agentic-sdlc workflow gates <run_id>
agentic-sdlc workflow decide <run_id> design_approval approve --actor <you> --reason "..." --payload '{"api_change_acknowledged": true}'
agentic-sdlc workflow run <run_id>
```

Run ids, timestamps and durations differ between runs; the stage table, the
skip reason, the retry sequence and the policy outcomes do not. The e2e test
`tests/e2e/test_scenarios.py` asserts that shape on every run of the suite.

## 5. What is demonstrated versus what is claimed

- **Demonstrated**: the control-plane behaviour above, executed through the
  same `Engine`, store and policy registry that the API uses.
- **Deterministic agents** (ADR-010): the `implement` stage writes red-test
  scaffolds and a change plan into an isolated run workspace
  (`data/runs/<run_id>/workspace/`); it does not modify the repository.
  Promotion into the codebase is a human act. The analytics-summary endpoint
  itself was built through the normal task plan (T-030s), not by the agent.
- **Decisions in the exported evidence were scripted** (`scenarios/__init__.py`)
  and replayed through `Engine.decide` under the `--actor` supplied on the
  command line. They are real decision records in the store, but they were
  not typed interactively at the moment of the run. The `--no-decide` path
  above is the interactive form.
- The transient fault is injected (`reason` says `(demo)`); measurements are
  demonstration data from a single local process.
