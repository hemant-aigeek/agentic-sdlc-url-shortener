# Gate 4 — Architecture and ADR Approval

- **Artifacts**: `specs/001-agentic-url-shortener/plan.md`, `research.md`,
  `data-model.md`, `docs/adr/ADR-001` … `ADR-011` (commit 7d5f92b)
- **Reviewer**: Hemant Gupta (candidate, architecture owner)
- **Date**: 2026-10-18
- **Decision**: APPROVED — all eleven ADRs moved from Proposed to Accepted.

## Per-ADR decision

| ADR | Decision | Note |
|---|---|---|
| 001 Modular monolith, two planes | Accepted | Planes share only persistence/telemetry; import rule is tested |
| 002 Python / FastAPI / Pydantic v2 | Accepted | Formalises the Gate 3 stack decision |
| 003 SQLite via SQLAlchemy behind ports | Accepted | Postgres is a documented path, not built |
| 004 Random base62 short codes | Accepted | 7 chars, bounded regeneration on collision |
| 005 Hand-built DAG + tick scheduler | Accepted | No workflow framework; parallelism via thread pool |
| 006 State rows + append-only event log | Accepted | Events are the reconstruction source of truth |
| 007 Gates as graph nodes | Accepted | `Engine.decide` is the only path past a gate |
| 008 Retry / fallback / safe-stop; rollback vs compensation | Accepted | Rollback only where the change is a reversible workspace write |
| 009 Graph-diff replanning | Accepted | Replan never skips a downstream gate |
| 010 Deterministic agents + run workspace | Accepted | LLM adapter deferred to backlog; workspace is the autonomy boundary |
| 011 Versioned in-code policy registry | Accepted | POLICY_VERSION recorded on every run |

## Conditions
- Any change to an accepted ADR requires a superseding ADR and a replan of
  affected tasks (constitution VII, X).
- Deferred items stay in `BACKLOG.md` and must not displace slices 1–9.
