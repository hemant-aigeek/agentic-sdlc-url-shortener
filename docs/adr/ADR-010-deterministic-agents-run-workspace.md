# ADR-010: Deterministic agents behind an Agent protocol; implementation in an isolated run workspace

## Status
Accepted — 2026-10-18 (Gate 4, docs/approvals/GATE-4-architecture.md)

## Context
"Agents" could be LLM calls or deterministic executors. The reviewer must be
able to re-run scenarios offline and get the same evidence; the candidate
chose determinism with a pluggable interface.

## Decision
- `Agent` protocol: `execute(ctx) -> StageResult`, optional `compensate(ctx)`.
- Each SDLC stage has a deterministic agent producing a structured artifact
  from the context (normalised requirement, quality checks, impact analysis
  computed from the real repository tree, decomposition, design with API/
  schema impact flags, change set, test plan, docs draft, security review,
  policy report, release decision, summary).
- `implement` applies a `ChangeSet` (files + inverse ops) to
  `data/runs/<run_id>/workspace/`; `verify` runs `python -m pytest` in that
  workspace as a subprocess with timeout; rejection reverts via recorded
  inverse ops. The live repository is never written by an agent; promoting a
  change set into the repository is a human commit — this is the controlled-
  autonomy boundary.
- An `LLMAgent` adapter implementing the same protocol is backlog.

## Options Considered
LLM agents (rejected at Gate 3: non-reproducible, needs keys, untestable
offline); deterministic agents that only emit documents (rejected: no real
apply/verify/revert evidence); agents writing to the repository directly
(rejected: violates human ownership of change).

## Consequences
- Positive: reproducible scenarios; real file operations and real test runs; honest about what is demonstrated.
- Negative: agents' "intelligence" is rule-based; stated plainly in docs.

## Risks and Mitigations
- Reviewer expects LLM → README states the choice and the adapter seam.

## Reversibility
Easy: swap agents per stage.

## Traceability
FR-O15..O18, AMB-08, EX-03, SCN-A/B/C.

## Validation
Agent unit tests; workspace apply/revert tests; scenario evidence.
