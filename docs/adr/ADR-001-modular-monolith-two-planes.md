# ADR-001: Modular monolith with separated application and control planes

## Status
Proposed (Gate 4 pending)

## Context
The assignment asks for a URL shortener *and* an orchestration system that
drives its SDLC, runnable locally in 2–3 days, with "production-grade
discipline, not production-scale infrastructure" (plan §12). Reviewers must be
able to see the separation between the thing being built and the thing that
builds it. Requirements: NFR-07, NFR-08, NFR-12, constitution VII.

## Decision Drivers
- Clean-clone runnability with no external services
- Visible separation of concerns for reviewers
- Testability of each plane in isolation
- Time: engine work must not be spent on deployment plumbing

## Options Considered
1. **Two services** (shortener service + orchestrator service, HTTP between them).
   + strongest boundary; − two processes, network config, doubled setup, no
   assessment value; − cross-service tests slower.
2. **Single package, single module tree** (everything under one namespace).
   + fastest; − boundaries erode under time pressure; − reviewer cannot tell
   planes apart.
3. **Modular monolith: one process, two sub-packages, shared persistence and
   telemetry, import rules enforced by a test.**
   + one command to run; + boundaries are explicit and *tested*; − a single
   SQLite file is shared (mitigated: no cross-plane foreign keys).

## Decision
Option 3. `src/agentic_sdlc/domain|api` form the application plane;
`orchestration|policy|scenarios` the control plane; `persistence|telemetry|
config` are shared. An architecture test asserts the import direction
(domain imports nothing internal; nothing imports api/cli).

## Rationale
Gives reviewers one process and one database to reason about while keeping the
planes separable enough to split later. The import test turns the boundary
into a failing build rather than a convention.

## Consequences
- Positive: single `agentic-sdlc serve`; shared test fixtures; simple Dockerfile.
- Negative: one process means orchestration load competes with redirect
  latency (irrelevant at assessment scale; documented).
- Operational: one SQLite file under `data/`.
- Testing: `tests/architecture/` enforces structure.
- Governance: changing the import rules requires superseding this ADR.

## Risks and Mitigations
- Boundary erosion → architecture test in the check script.
- Shared DB coupling → separate tables, no cross-plane FKs, separate repositories.

## Reversibility
Medium-easy: the control plane depends on the application plane only through
the filesystem workspace and the repository on disk, so extraction is a
packaging exercise.

## Traceability
NFR-07, NFR-08, NFR-12; spec §2 Journey 5; plan §Project Structure; tasks T-BASE-*.

## Validation
Architecture tests pass; clean-clone run recorded in `docs/evidence/clean-clone.md`.
