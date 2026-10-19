# Scenario B — Brownfield: a change to existing behaviour is analysed before it is touched

**Requirement id**: SCN-B · **Evidence**: [`docs/evidence/brownfield/`](../evidence/brownfield/README.md) (run `01a1502e31fc508fb3153c49e9`) · **Terminal**: `COMPLETED` / release `READY`

## 1. Input

> Expired links must return 410 Gone instead of the current 404, and analytics
> for expired links must remain readable.

Submitted with `scope=brownfield`. No demonstration faults.

## 2. What the assignment asks this scenario to prove

Before any code changes, the system must identify impacted components,
interfaces, data flows, tests, documentation, regression risks and
rollout/rollback considerations — derived from the **actual repository**, and
the change-control policy must require that analysis to exist.

## 3. Path shape

```
ingest → quality_check ─(SKIPPED, no ambiguity)→ impact_analysis → decompose → design
       → [design_approval · HUMAN] → { implement ‖ test_plan ‖ docs_draft } → verify
       → security_review → compliance_check (CHG-001 PASS) → [release_readiness · HUMAN] → summary
```

The only structural difference from Scenario A is the `impact_analysis`
node, which is conditional on `scope == brownfield` and sits *before*
decomposition so that the task breakdown is derived from the impact map rather
than the other way round.

| Property under assessment | Where to look in the evidence |
|---|---|
| Impact analysis executed before any change | `events.json` seq 10–12: `impact_analysis` ready/started/succeeded before `decompose` (seq 13) |
| Impact derived from the repository, not from the requirement text | `artifacts.json` → kind `impact_analysis` → `evidence.files_scanned: 164`, `files_matched: 45`, `match_detail` lists the exact paths and the terms (`410`, `404`, `expir`, `analytics`, `RedirectEvent`) that matched |
| Impacted modules / interfaces / tests / docs enumerated | same artifact: `impacted_modules`, `impacted_control_plane_modules`, `impacted_interfaces` (OpenAPI paths), `impacted_data_flows`, `impacted_tests`, `impacted_docs`, `data_compatibility` ("no persistence schema change; stored rows remain valid") |
| Regression risk and rollback stance | same artifact: `regression_risks`, `rollback_considerations` |
| Decomposition inherits the impact map | `artifacts.json` → kind `decomposition` → `components` list equals the impacted modules; tasks are red/green pairs per acceptance criterion |
| Change-control policy enforced | `policy.json` → `CHG-001 PASS — impact analysis recorded before implementation` (it is `NOT-APPLICABLE` in Scenario A, which is how the policy proves it is scope-aware) |
| API contract impact acknowledged by a human | `decisions.json` → `design_approval` payload `api_change_acknowledged: true`; `CHG-002 PASS` |
| Terminal outcome | seq 45 `run_completed COMPLETED`; `scenario.json` → `READY` |

## 4. The brownfield change itself

The requirement in this scenario is also real in the repository: the 410
behaviour and readable analytics for expired links are implemented in
`domain/service.py` and `api/routers/redirect.py` and covered by
`tests/contract/test_links_api.py` and `tests/unit/test_service.py`
(FR-U06, FR-U08). The commit `feat(redirect): …` in the history shows the
test-first sequence. The orchestrated run above is the governance record that
*would* precede such a change; the two are kept separate deliberately so that
the evidence cannot be mistaken for the agent having edited the codebase.

## 5. Re-running it

```bash
agentic-sdlc scenario run brownfield --actor <your-name> --export /tmp/evidence
# the impact analysis alone, interactively:
agentic-sdlc workflow start "@docs/scenarios/brownfield.md" --scope brownfield --no-run
agentic-sdlc workflow run <run_id> --max-batches 3     # stops after impact_analysis
agentic-sdlc workflow inspect <run_id>
```

## 6. What is demonstrated versus what is claimed

- The impact scan is a deterministic term-and-symbol search over the working
  tree (see `orchestration/agents/analysis.py`). It finds every file that
  mentions the affected behaviour; it does not perform semantic call-graph
  analysis. The `search_needles` and `terms` fields show exactly what was searched for; that is the honest level
  for a deterministic agent. An LLM-backed agent (BACKLOG) would plug in at the
  same `Agent` protocol and could reason about the matches.
- Decisions in the export were scripted and replayed under `--actor`; see the
  note in [greenfield.md](greenfield.md) §5.
