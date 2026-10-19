# Agentic SDLC — URL Shortener

A governed, stateful, non-linear agentic orchestration system that takes a
software requirement through the SDLC — requirement understanding, ambiguity
detection, decomposition, design, implementation, testing, documentation,
security and compliance checks, release readiness and a final engineering
summary — with humans owning every approval. A small, production-disciplined
URL shortener is the system it builds and changes.

> Start with [`docs/reviewer-guide.md`](docs/reviewer-guide.md): every claim in
> this repository maps there to a path, a command and an expected result.
> Nothing in the documentation describes behaviour that is not implemented and
> tested.

## Deliverables at a glance

| Assignment deliverable | Where |
|---|---|
| Working prototype, runnable end-to-end | `pip install -e ".[dev]" && ./scripts/check.sh && agentic-sdlc serve` (§Setup) |
| Architecture overview | [`docs/architecture.md`](docs/architecture.md) · decisions in [`docs/adr/`](docs/adr/README.md) |
| Three scenarios — greenfield, brownfield, ambiguous | [`docs/scenarios/`](docs/scenarios/) walkthroughs · executed evidence in [`docs/evidence/`](docs/evidence/) |
| Setup instructions | §Setup below · [`specs/001-agentic-url-shortener/quickstart.md`](specs/001-agentic-url-shortener/quickstart.md) |
| Testing approach, limitations, trade-offs | [`docs/testing.md`](docs/testing.md) · [`BACKLOG.md`](BACKLOG.md) |
| Final engineering summary | [`docs/final-engineering-summary.md`](docs/final-engineering-summary.md) |
| Requirement → task → test → evidence traceability | [`docs/traceability.md`](docs/traceability.md) (generated, build fails on orphans) |

## What the orchestrator does

- **Explicit dependency graph per run** — stages with entry/exit gates,
  conditional branches, parallel fan-out and join; inspectable over the API
  (`/graph`) and in every evidence export.
- **Persisted state + append-only audit log** — a run can be inspected,
  reconstructed from events alone, and resumed by a fresh process after
  interruption.
- **Human gates as graph nodes** — clarification, design approval, policy
  exception, release readiness. No decision → no progress; a gate timeout is a
  safe-stop, never an approval. Every decision is attributable.
- **Reliability controls** — transient/permanent failure classification,
  bounded retry with backoff and per-attempt timeout, per-stage fallback,
  compensation in reverse dependency order, true rollback for workspace
  writes, deterministic safe-stop.
- **Dynamic replanning** — a clarification or changed requirement rebuilds the
  graph, diffs it, invalidates exactly the affected downstream stages and
  regenerates their gates; before/after graphs are recorded.
- **Versioned policy enforcement** — security, compliance, change-control and
  dependency policies evaluated per run with `PASS | FAIL |
  EXCEPTION-REQUESTED | NOT-APPLICABLE`; a failed mandatory policy blocks
  release; exceptions need a human approver, a compensating control and an
  expiry.
- **Measurements** — success/failure rate, retries, fallbacks, compensations,
  safe-stops, replans, recovery durations, MTTR (recovered events only) and
  end-to-end latency, labelled as demonstration data.
- **Deterministic agents behind an `Agent` protocol** — reproducible offline;
  the LLM adapter is the documented extension point (ADR-010). Agents write
  into an isolated run workspace; promoting code into the repository is a
  human act.

## The URL shortener (application plane)

Create, redirect, expire (`410 Gone`), per-link analytics, idempotency keys,
health/readiness, API-key auth on mutating endpoints, in-process rate
limiting. URL validation enforces an `http`/`https` allow-list and rejects
loopback, link-local, private, ULA and cloud-metadata targets. All errors are
RFC 9457 `application/problem+json` with a correlation ID. The contract is
versioned (`specs/001-agentic-url-shortener/contracts/openapi.yaml`) and
drift-checked in the test suite.

## Setup

Requires Python 3.12+. No external services.

```bash
git clone https://github.com/hemant-aigeek/agentic-sdlc-url-shortener.git
cd agentic-sdlc-url-shortener
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
./scripts/check.sh          # ruff, mypy --strict, 290 tests, contract drift, secret scan, licences
agentic-sdlc serve          # API + interactive docs at http://127.0.0.1:8000/docs
```

Then, in another shell:

```bash
agentic-sdlc scenario list                                   # the three scenarios + four control demos
agentic-sdlc scenario run ambiguous --actor you --no-decide  # stops at the clarification gate
agentic-sdlc workflow gates <run_id>                         # see the ambiguities and options
agentic-sdlc workflow decide <run_id> clarification clarify --actor you \
    --reason "30-day TTL; never reuse codes" \
    --payload '{"answers": {"AMB-R1": "ttl_30d", "AMB-R2": "reuse_never"}}'
agentic-sdlc workflow events <run_id>                        # the audit trail, including the replan
```

Configuration is via environment variables (`.env.example`); defaults are
safe for local use.

## Repository map

| Path | Purpose |
|---|---|
| `src/agentic_sdlc/domain`, `api/routers/{links,redirect,health}.py`, `persistence/link_repository.py` | Application plane |
| `src/agentic_sdlc/orchestration/` | Control plane: graph, state machines, engine/scheduler, agents, planner, metrics, evidence export, workspace |
| `src/agentic_sdlc/policy/` | Versioned policy registry and evaluator |
| `src/agentic_sdlc/api/routers/{workflows,decisions,metrics}.py` | Control-plane HTTP API |
| `src/agentic_sdlc/cli.py`, `scenarios/` | CLI and replayable scenario definitions |
| `tests/` | unit · contract · integration · orchestration · security · e2e · architecture (290 tests) |
| `specs/001-agentic-url-shortener/` | Specification, clarifications, plan, research, data model, contracts, tasks |
| `.specify/memory/constitution.md` | Engineering constitution the work was held to |
| `docs/adr/` | Eleven accepted architecture decision records |
| `docs/approvals/` | Human gate decisions (constitution, spec, clarifications, architecture, release) |
| `docs/evidence/` | Executed run exports (events, graph, decisions, policy, metrics, artifacts) + repository release check |
| `docs/reviews/` | Independent assessment of the submission |
| `scripts/` | `check.sh` quality gate, release check, contract export, traceability, secret and licence scans |

## Process

The repository was built with a SpecKit lifecycle and explicit human gates:
constitution → specification → clarification → plan + ADRs → checklists →
tasks → analysis → test-first implementation in checkpointed task groups →
scenario evidence → convergence → independent review → release decision.
The commit history is the execution record: each behaviour group lands as a
`test(...)` commit followed by its `feat(...)` commit. AI coding assistance
was used throughout under that process; every material decision is recorded
in `docs/approvals/` and `docs/adr/` with its alternatives and reasoning.
