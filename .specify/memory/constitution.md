# Agentic SDLC URL Shortener — Engineering Constitution

This repository is an interview assessment submission. The URL shortener is the
demonstration domain; the thing under evaluation is a governed, stateful,
non-linear agentic orchestration system that turns a requirement into a
reviewable engineering outcome. Every principle below exists to keep that
distinction honest.

## Core Principles

### I. Specification Before Implementation
- No production code is written for a behaviour that does not have an approved
  requirement ID (FR-xxx / NFR-xxx / SCN-x) in `specs/`.
- Requirements are testable. If a requirement cannot be verified by a test, a
  demonstration command, or a reviewer-visible artifact, it is rewritten or
  removed.
- Functional and non-functional requirements are kept in separate sections and
  never merged into one line.
- Ambiguity is resolved through `/speckit.clarify` with a recorded human
  decision, or recorded as an explicit assumption with an owner. It is never
  resolved silently in code.
- A material upstream change (requirement, contract, schema, state model)
  triggers downstream impact analysis before implementation resumes.
- Existing code is never treated as the specification.

### II. Explicit, Stateful, Non-Linear Orchestration
- The orchestration layer MUST be modelled as an explicit dependency graph of
  stages, not an ordered list of function calls.
- The graph MUST support: sequential paths, parallel fan-out, join
  synchronisation, conditional branching, suspension, resumption, and dynamic
  replanning when an upstream output changes.
- Every stage defines: purpose, inputs, outputs, entry criteria, exit criteria,
  owning actor (agent or human), timeout, retry policy, failure classification,
  fallback, and the audit events it emits.
- Workflow state, cross-stage context, artifact provenance, and decision
  lineage are persisted so that a run can be inspected and resumed after
  process restart.
- Agent autonomy is bounded: an agent may act only within the stage it owns and
  may not transition the workflow past a human gate.

### III. Human Governance
- Humans own: interpretation of material ambiguity, architecture approval,
  technology selection, security-sensitive decisions, destructive or
  irreversible changes, acceptance of material risk, constitutional exceptions,
  release readiness, and final submission.
- High-impact actions require explicit, recorded human approval
  (actor, decision, timestamp, reason).
- Approval, rejection, escalation, timeout, and safe-stop behaviour is defined
  for every gate. Silence is never approval; a gate that times out moves to
  safe-stop, not to the next stage.
- Mandatory gates cannot be skipped by configuration.

### IV. Test-Driven Engineering
- Domain and orchestration behaviour is built red → green → refactor: a failing
  test is written and executed first, its failure reason is confirmed, the
  smallest compliant implementation is added, then refactoring happens only
  while green.
- Test levels required: unit (domain), API contract, persistence, orchestration
  state-transition, reliability (retry/timeout/fallback/compensation/safe-stop/
  resume/replan), security, and end-to-end scenario tests.
- A task is complete only when its validation command was actually executed
  and passed. Generated-but-unrun code is not done.
- Implementation-first work is never retroactively described as TDD.

### V. Security and Privacy by Design
- All external input is validated and normalised before use.
- Only `http` and `https` target URLs are accepted; redirect targets resolving
  to loopback, link-local, private, or metadata address ranges are rejected to
  prevent SSRF-style abuse through the redirector.
- Secrets never appear in logs, audit events, or committed files.
- Secure defaults: least privilege, explicit trust boundaries, rate-limiting
  hooks, and documented authentication assumptions.
- Release readiness includes dependency and secret scanning results.

### VI. Compliance and Change-Control Policy Enforcement
- Policy guardrails (security, compliance, privacy, audit retention, approved
  dependencies, licensing, change control) are versioned artifacts, not
  comments in code.
- Every orchestration run records the policy version it was evaluated against.
- Every policy check produces exactly one outcome:
  `PASS` | `FAIL` | `EXCEPTION-REQUESTED` | `NOT-APPLICABLE`.
- A failed mandatory policy blocks downstream progression. An exception
  requires explicit human approval and records: policy, reason, scope,
  approving authority, compensating control, approval timestamp, and expiry or
  review condition.
- Changes to approved requirements, architecture, schemas, workflow states,
  security controls, or release criteria pass through impact analysis and
  change approval.
- Release readiness FAILS while a mandatory policy is violated or an exception
  is unapproved or expired.

### VII. Architecture and Maintainability
- Domain logic, API delivery, persistence, orchestration, policy enforcement,
  telemetry, and configuration are separate modules with explicit interfaces.
- Material decisions and rejected alternatives are recorded as ADRs in
  `docs/adr/`. An ADR is `Accepted` only after explicit human approval.
- Complexity must be justified by a requirement or by demonstrability.
  Production-grade discipline is required; production-scale infrastructure is
  not.
- Code is modular, readable, typed, and replaceable.

### VIII. Reliability and Recovery
- Failures are classified as transient or permanent; only transient failures
  are retry-eligible.
- Retries are bounded, with defined backoff and per-attempt timeout.
- Repeatable operations are idempotent and protected against duplicate
  execution.
- Fallback behaviour is defined per stage.
- Rollback (undo a reversible change) and compensation (counteract an
  irreversible one) are distinguished and chosen deliberately.
- Safe-stop conditions are explicit; safe-stop is a deterministic terminal
  state with recorded reason.
- Interrupted runs resume from persisted state, not from the beginning.
- Success, failure, retry, compensation, recovery duration, and latency are
  captured as evidence.

### IX. Observability and Auditability
- Every run has a correlation ID carried through logs, events, and metrics.
- State transitions, decisions, approvals, rejections, retries, failures,
  replanning events, and terminal outcomes are recorded as audit events with
  actor type, action, timestamp, affected artifact or state, result, and reason.
- Logs, metrics, and the event history together allow a run to be
  reconstructed without the original process.
- Demonstration measurements are labelled as such and never presented as
  production statistics.

### X. Traceability and Repository Integrity
- Traceability is bidirectional across:
  Requirement → Scenario → Design → ADR → Task → Code → Test → Validation →
  Documentation → Evidence.
- Commits are small and coherent; messages describe engineering intent in
  conventional-commit form.
- Approval, test, execution, and operational evidence is never fabricated.
  Illustrative examples are labelled as illustrative.
- AI-generated artifacts are reviewed and owned by the human candidate.
- Documentation is updated in the same change as the behaviour it describes.

### XI. Evidence-Based Completion
A feature or task is complete only when all of the following hold:
1. Applicable requirement IDs are identified.
2. Decisions and assumptions are recorded.
3. Acceptance criteria are satisfied.
4. Required tests were executed and passed.
5. Security and reliability checks are complete.
6. Documentation is current.
7. Traceability is updated.
8. Residual risks and limitations are disclosed.
9. Required approvals are recorded.
10. Evidence is available for reviewer verification in the repository.

## Assessment Constraints

- Timebox: 2–3 days. Must-have scope is defined in the plan; optional work is
  recorded in `BACKLOG.md` and never displaces mandatory validation or
  reviewer evidence.
- The system must run locally end-to-end from a clean clone with the commands
  in `README.md`.
- The URL shortener is deliberately minimal (create, redirect, expire,
  analytics, health). Depth goes into orchestration, governance, reliability,
  and evidence.

## Governance

- **Precedence.** When instructions conflict: official assessment requirements
  → this constitution → approved specification and clarifications → approved
  plan and contracts → accepted ADRs → task plan → current implementation →
  conversation.
- **Compliance review.** `/speckit.plan` includes a Constitution Check section;
  `/speckit.analyze` and `/speckit.converge` report violations by severity
  (CRITICAL / HIGH / MEDIUM / LOW). A CRITICAL finding blocks progression.
- **Exceptions.** A principle may be waived for a bounded scope only through a
  recorded exception approved by the human candidate, with reason,
  compensating control, and expiry. Principles III (Human Governance), X
  (Repository Integrity), and XI (Evidence-Based Completion) cannot be waived.
- **Conflicts between principles.** Resolve in favour of the principle that
  preserves human authority and evidence integrity; record the resolution as a
  decision in the affected ADR or clarification log.
- **Amendments.** Versioned with semantic versioning: MAJOR for removing or
  redefining a principle, MINOR for adding a principle or section, PATCH for
  wording. Each amendment records date and rationale below.
- **Release readiness.** Fails while any mandatory principle is violated, any
  mandatory policy is failed or has an unapproved exception, or any CRITICAL
  analysis finding is open.

**Version**: 1.0.0 | **Ratified**: 2026-10-15 | **Last Amended**: 2026-10-15

### Amendment Log
- 1.0.0 (2026-10-15): Initial ratification for the assessment.
