# Agentic SDLC — URL Shortener

A governed, stateful, non-linear agentic orchestration system that takes a
software requirement through the SDLC — requirement understanding, ambiguity
detection, decomposition, design, implementation, testing, documentation,
security and compliance checks, release readiness, and a final engineering
summary — with humans owning the approvals. A small production-disciplined
URL shortener is the system it builds and changes.

> Status: under construction (assessment timebox, day 1 of 3). This README
> grows with the code; nothing here describes behaviour that is not yet
> implemented and tested.

## What is in the repository

| Path | Purpose |
|---|---|
| `src/agentic_sdlc/domain`, `api`, `persistence/link_repository.py` | Application plane: the URL shortener |
| `src/agentic_sdlc/orchestration`, `policy`, `persistence/workflow_store.py` | Control plane: dependency graph, state machine, scheduler, gates, reliability, replanning, policy enforcement |
| `specs/001-agentic-url-shortener/` | Specification, clarifications, plan, data model, tasks (SpecKit lifecycle) |
| `docs/adr/` | Architecture decision records (accepted at Gate 4) |
| `docs/approvals/` | Human gate decisions |
| `docs/` (architecture, scenarios, testing, traceability, reviewer-guide, final summary) | Added as the corresponding work lands |
| `scripts/check.sh` | The quality gate: lint, types, tests, contract drift, secret scan, licences |

## Setup

Requires Python 3.12+.

```bash
git clone https://github.com/hemant-aigeek/agentic-sdlc-url-shortener.git
cd agentic-sdlc-url-shortener
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
./scripts/check.sh          # full quality gate
agentic-sdlc serve          # API at http://127.0.0.1:8000/docs
```

## Current capabilities

- `GET /health/live`, `GET /health/ready` (readiness checks the database)
- All errors are RFC 9457 `application/problem+json` with a correlation ID
- Import-direction rule between planes enforced by `tests/architecture`

## Process

The repository follows a SpecKit lifecycle with explicit human gates:
constitution → specification → clarification → plan + ADRs → tasks →
test-first implementation in checkpointed task groups → scenario evidence →
convergence → independent review → release decision. Gate records live in
`docs/approvals/`; the task graph in `specs/001-agentic-url-shortener/tasks.md`.
