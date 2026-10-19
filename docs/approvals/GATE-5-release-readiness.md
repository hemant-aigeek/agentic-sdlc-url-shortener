# Gate 5 — Release-Readiness Decision (assessment submission)

- **Artifacts reviewed**: `docs/evidence/release-check.json` (READY),
  `docs/evidence/clean-clone.md`, `docs/reviews/final-assessment.md`,
  `docs/final-engineering-summary.md`, `docs/traceability.md` (0 orphans),
  the seven scenario exports under `docs/evidence/`.
- **Decider**: Hemant Gupta (candidate, release owner)
- **Date**: 2026-10-19

## Inputs to the decision

| Check | Result |
|---|---|
| Quality gate (`./scripts/check.sh`) | PASS — 298 tests, mypy strict, ruff, contract drift, secret scan, licences |
| Dependency audit (`pip-audit`) | PASS — no known vulnerabilities |
| Scenario evidence (3 scenarios + 4 control demos) | all present with expected terminal states; reproduced on a clean clone |
| Independent assessment | PASS after disposition; 2 mandatory findings, both fixed test-first (`706812a`→`f597286`, `fc58318`→`16e7f5d`) |
| Open CRITICAL/HIGH analysis findings | none |
| Unapproved or expired policy exceptions in evidence | none (one approved, unexpired exception in SCN-C, by design) |
| Constitution principles III, X, XI (non-waivable) | satisfied — every gate recorded, no fabricated evidence, completion criteria met |

## Accepted limitations (carried into the decision)

1. Deterministic rule-based agents; LLM adapter deferred (AMB-08, ADR-010).
2. Single-process execution; per-run serialisation inside the process, no
   cross-process lease (ADR-005, review item 5).
3. Literal SSRF checks; no DNS resolution (AMB-03).
4. Best-effort analytics; loss on crash (AMB-05).
5. Gate timeouts evaluated on the next tick, not by a background timer.
6. `engine.py` size — refactor debt, not a defect.

## Decision

**READY WITH ACCEPTED LIMITATIONS** — the prototype satisfies every mandatory
assignment requirement with executed evidence; the limitations above are
recorded choices with documented paths, none of which weakens a required
control.

Tag applied: `assessment-submission-v1.0`.
