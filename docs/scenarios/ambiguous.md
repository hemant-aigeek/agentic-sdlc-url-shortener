# Scenario C — Ambiguous requirement: suspend, clarify, replan, resume

**Requirement id**: SCN-C · **Evidence**: [`docs/evidence/ambiguous/`](../evidence/ambiguous/README.md) (run `01a1502f681045c398f321de78`) · **Terminal**: `COMPLETED` / release `READY WITH ACCEPTED LIMITATIONS`

## 1. Input

> Links should expire after a while and be reusable.

Submitted with `scope=auto` (the engine classifies it). One demonstration
fault is enabled: the automated `security_review` fails permanently
(`AGENTIC_DEMO_FAULT_SECURITY_PERMANENT_FAILURE=true`) so that fallback,
`EXCEPTION-REQUESTED` and the policy-exception gate are exercised in the same
run.

## 2. What the assignment asks this scenario to prove

Detect the ambiguity · prevent unsafe implementation · request human
clarification · record the decision · identify downstream impact · update the
affected artifacts · resume at the correct state.

## 3. Path shape

```
ingest → quality_check (2 ambiguities, max severity HIGH)
       → [clarification · HUMAN]  ← run is WAITING_CLARIFICATION; nothing downstream exists yet
       → REPLAN v1→v2: requirement_revision inserted; 14 downstream stages INVALIDATED → regenerated
       → requirement_revision (v2 passes all checks) ─(scope ≠ brownfield → impact_analysis SKIPPED)→ decompose → design
       → [design_approval · HUMAN] → { implement ‖ test_plan ‖ docs_draft } → verify
       → security_review ✗ PERMANENT → fallback manual_security_review (FALLBACK)
       → compliance_check: SEC-003 = EXCEPTION-REQUESTED → [policy_exception · HUMAN]
       → [release_readiness · HUMAN] → summary
```

| Required evidence item (assignment / guide §20) | Where to look |
|---|---|
| 1. Original ambiguous input | `run.json` → `requirement` (version 1) |
| 2–3. Detected ambiguity, classification, severity | `artifacts.json` → kind `quality_check`: `AMB-R1` *undefined_quantity* ("a while", HIGH) and `AMB-R2` *conflict* with FR-U04 ("reusable" vs. code uniqueness), each with options and their engineering impact |
| 4. Affected requirements / components | `AMB-R2.conflicts_with: FR-U04`; options list the impact per choice (e.g. "weakens FR-U04; needs grace-period rule") |
| 5–7. State before detection → blocked state, and why | `events.json` seq 8 `quality_check SUCCEEDED` → seq 9 `gate_opened clarification WAITING — human resolves material ambiguity before any design or implementation`; `graph.json` version 1 has no `requirement_revision` stage and `decompose` depends on the gate, so no implementation stage can become ready |
| 8–9. Clarification request and recorded human decision | `decisions.json` → gate `clarification`, decision `clarify`, payload `answers: {AMB-R1: ttl_30d, AMB-R2: reuse_never}`, reason "expire 30 days after creation; short codes are never reused (FR-U04 stands)" |
| 10. Updated requirement / assumption | `artifacts.json` → kind `requirement_revision`: `requirement_version: 2`, `resolved: [AMB-R1, AMB-R2]`, `remaining_high_ambiguities: []`, all four quality checks `passed` |
| 11–13. Downstream impact, replanning event, invalidated and regenerated artifacts | `replans.json`: trigger `clarification at clarification`, `invalidated` lists 14 stages, `graph_before` (v1) vs `graph_after` (v2 — `requirement_revision` inserted between the gate and `impact_analysis`); `events.json` seq 11 `replan v2`; `run.json` → `graph_version: 2`, `requirement_version: 2` |
| 14. Resumed workflow state | seq 12: the first stage to become ready after the replan is `requirement_revision`, not `ingest` — succeeded upstream stages are not re-run |
| 15. Final validation | seq 34–35 `verify SUCCEEDED`; `policy.json` 8 × PASS / N-A |
| Fallback on permanent failure (bonus path) | seq 38–42: `failure_detected PERMANENT` → `stage_failed` → `fallback_used` → `recovery_completed RECOVERED`; stage state `FALLBACK` |
| Policy exception with compensating control and expiry | `policy.json` → `SEC-003 EXCEPTION-REQUESTED`; `exceptions`: approver, compensating control "manual security checklist reviewed and attached", `expires` 30 days later |
| 16–17. Audit trail and terminal outcome | 54 ordered events with actor type; seq 54 `run_completed`; `scenario.json` → `outcome.release_decision: READY WITH ACCEPTED LIMITATIONS` (the approved exception is the accepted limitation) |

## 4. Why the replan is governed, not a shortcut

- The replan does not edit the live graph in place. It produces a new graph
  version from the planner with the recorded clarification as an input, diffs
  it against the current version, invalidates exactly the stages whose inputs
  changed, and records before/after (ADR-009).
- Every downstream gate is regenerated with the invalidated stages:
  `design_approval`, `policy_exception` and `release_readiness` all had to be
  decided *after* the replan (seq 23, 47, 50). A replan can never carry an
  approval forward past a changed input.
- The clarification itself cannot be auto-approved: `Engine.decide` is the only
  code path out of a gate node (ADR-007), and the scheduler never calls it.

## 5. Re-running it interactively (the honest version)

```bash
agentic-sdlc scenario run ambiguous --actor <your-name> --no-decide
# → prints the open gate and the exact decide command, e.g.
agentic-sdlc workflow gates <run_id>                   # shows AMB-R1 / AMB-R2 with options
agentic-sdlc workflow decide <run_id> clarification clarify --actor <you> \
    --reason "30-day TTL; never reuse codes" \
    --payload '{"answers": {"AMB-R1": "ttl_30d", "AMB-R2": "reuse_never"}}'
agentic-sdlc workflow run <run_id>                      # replans, then stops at design_approval
```

Choose `reuse_after_expiry` instead and the revised requirement carries a
recorded conflict with FR-U04 that the design stage must address — the run
does not silently pick the convenient interpretation.

## 6. What is demonstrated versus what is claimed

- Ambiguity detection is rule-based (`agents/requirements.py`): undefined
  quantities, conflicts with approved requirement ids, missing observable
  outcomes. It is sufficient to detect the two ambiguities in this input and
  to pass the revised requirement; it is not a general natural-language
  analyser. The LLM adapter in the backlog would replace this detector behind
  the same protocol and emit the same `ambiguities[]` schema.
- The security failure is injected and labelled `(demo)`.
- Decisions in the export were scripted and replayed under `--actor` (see
  [greenfield.md](greenfield.md) §5); the §5 commands above are the
  interactive form a reviewer should use to see the gate actually block.
