# Final Independent Assessment

**Scope**: the full repository at commit `e29acd5` (pre-review baseline) —
assignment requirements, constitution, specification, clarifications, plan,
contracts, ADRs, tasks, source, tests, scenario evidence, documentation, Git
history. **Method**: skeptical principal-engineer review; nothing was credited
from documentation alone. The quality gate, the seven scenarios and a sample
of `docs/reviewer-guide.md` rows were executed; the API was probed for gate
bypass, SSRF bypass and scheduler races. **Rule**: findings were fixed only
within approved requirements and architecture; each fix landed as a red test
commit followed by the fix commit, and is listed in §Disposition below.

## Overall Verdict: PASS (after disposition of two mandatory findings)

## Executive Rationale

The differentiator the assignment grades — governed, stateful, non-linear
orchestration — is real: the graph is explicit and inspectable, parallel
fan-out shows overlapping timestamps in executed evidence, joins and
conditional skips are recorded with reasons, gates cannot be passed by any
code path other than an attributable `decide`, replanning produces a diffable
graph version and regenerates downstream gates, and resume/safe-stop/
fallback/compensation are all demonstrated by executed runs that a reviewer
can regenerate offline. Evidence integrity is unusually good: injected faults
are labelled, scripted decisions are disclosed, demonstration measurements
are labelled, and the traceability matrix is generated and enforced in the
suite.

Two defects were found by probing rather than reading, both of a kind a
production reviewer would block on: an SSRF bypass through abbreviated numeric
hosts (`http://127.1/`) and trailing-dot hostnames (`localhost.`), and
duplicate stage execution when two callers advance the same run concurrently.
Both are fixed test-first (commits `f597286`, `16e7f5d`). With those
dispositioned, nothing mandatory remains open.

## Scoring Matrix (0–5)

| Dimension | Score | Basis |
|---|---|---|
| Requirement understanding | 5 | spec separates confirmed / derived / assumptions / ambiguities / exclusions with stable ids |
| Ambiguity management | 4 | rule-based detector finds the planted ambiguities and blocks; not a general analyser (disclosed) |
| Task decomposition | 4 | decomposition artifact has dependencies, parallel flags, red/green pairs; repo tasks.md is dependency-aware |
| Brownfield reasoning | 4 | impact analysis scans the real tree before any change; term-based, not semantic (disclosed) |
| Orchestration effectiveness | 5 | graph + scheduler + gates + reliability + replan all executed, not described |
| Stateful & non-linear design | 5 | persisted rows + events; conditional branches, fan-out/join, replan |
| Parallel execution & synchronization | 5 | overlapping timestamps in evidence; join asserted by test |
| Controlled autonomy | 5 | agents write to an isolated workspace; promotion is human; gates are nodes |
| Human approval enforcement | 5 | no-decision → no progress; forged row test; actor required; timeout → safe-stop |
| Retry / fallback / timeout / safe-stop | 5 | bounded, classified, tested and demonstrated |
| Rollback or compensation | 4 | honest split: true rollback for workspace writes, compensation otherwise |
| Resume & recovery | 4 | fresh-engine resume demonstrated; no background timer for gate timeouts |
| Dynamic replanning | 5 | graph diff with before/after; gates regenerated; resumes at first invalidated stage |
| Decision lineage | 4 | `derived_from` + policy version on every artifact |
| Traceability | 5 | generated matrix, 0 orphans, enforced in suite |
| Architecture quality | 4 | two planes with tested import rule; `engine.py` is large |
| Code quality | 4 | typed (mypy strict), linted, small modules; engine would benefit from a split |
| TDD | 4 | test→feat commit pairs throughout; a few property/parametrised additions same-commit (disclosed) |
| Test depth | 4 | 298 tests incl. races, forged rows, reconstruction; benchmark is demo-only |
| Security | 3 → 4 | SSRF bypass found and fixed; DNS resolution still deferred (recorded) |
| Reliability | 3 → 4 | duplicate execution found and fixed in-process; multi-process lease still deferred (recorded) |
| Observability | 4 | correlation ids, structured logs, metrics incl. MTTR formula; no tracing export |
| Auditability | 5 | append-only sequenced events with actor type; reconstruction tested |
| Greenfield scenario | 5 | skip-with-reason, fan-out, retry, MTTR — all in executed evidence |
| Brownfield scenario | 4 | impact analysis before change, CHG-001 scope-aware |
| Ambiguous scenario | 5 | block → clarify → replan → resume → exception → accepted limitations |
| Documentation | 4 | reviewer guide verified row by row; a handful of field-name drifts were corrected during review |
| GitHub evidence | 4 | ~60 coherent conventional commits; lifecycle visible; no squash |
| Defensibility of decisions | 5 | 11 ADRs with options/consequences/reversibility; Gate 3 rationale per ambiguity |
| Engineering judgment | 5 | depth over breadth; determinism over flair; limitations stated before being asked |

## Mandatory Blocking Gaps (found → disposition)

1. **SSRF bypass via abbreviated numeric hosts and trailing-dot names.**
   `POST /api/v1/links` accepted `http://127.1/`, `http://0x7f.1/`,
   `http://0177.0.0.1/`, `http://10.1/`, `http://localhost./` and
   `http://metadata.google.internal./`. libcurl and browsers expand the
   numeric forms to loopback/private addresses; the trailing dot is the FQDN
   spelling of a blocked name. `src/agentic_sdlc/domain/validation.py` only
   caught canonical literals. **Fixed**: red tests `tests/unit/test_validation.py`
   (`706812a`), fix in `validation.py` (`f597286`).
2. **Duplicate stage execution under concurrent advancement.** Three threads
   calling `Engine.run(run_id)` on the same run executed `ingest`,
   `quality_check`, `decompose`, `design` three times each (`stage_started`
   ×3 per stage). The store lock protected persistence but not the
   ready-set decision. **Fixed**: red test
   `tests/orchestration/test_reliability.py::test_concurrent_run_calls_on_one_run_execute_each_stage_once`,
   per-run re-entrant lock around `run/decide/resume/stop/replan` (`16e7f5d`).
   Cross-process protection (lease column) remains a recorded limitation.

## Evidence Strengths

- Executed, regenerable evidence for every control, with injected faults
  labelled `(demo)` in the event reason itself.
- Gate bypass attempts fail correctly: no actor → 401; wrong gate → 409;
  invalid decision → 422; double decision → 409; `resume` on a waiting run
  does not advance; approving a design with API impact *without* the
  acknowledgement payload yields `CHG-002 FAIL` and opens the
  `policy_exception` gate rather than passing silently.
- Clean-clone verification recorded with real figures
  (`docs/evidence/clean-clone.md`).

## Unsupported Claims (found during review; all corrected before this record)

- `docs/scenarios/brownfield.md` cited artifact fields `modules`, `interfaces`,
  `rollout_rollback`, `method` that do not exist (actual:
  `impacted_modules`, `impacted_interfaces`, `rollback_considerations`,
  `search_needles`). Corrected.
- `docs/testing.md` originally attributed Hypothesis property tests to URL
  validation (they exist for short codes only) and said engine tests use an
  on-disk store (they use the real store on in-memory SQLite). Corrected.
- `docs/reviewer-guide.md` originally showed `302` for redirects (actual
  `307`), `short_code` (actual `code`), `by_day` (actual `redirects_by_day`).
  Corrected after executing the commands.
- `specs/001-agentic-url-shortener/quickstart.md` referenced CLI commands that
  did not exist (`run-scenario`, `export-evidence` at top level). Rewritten.

## Architecture Concerns

- `orchestration/engine.py` (~1.3k lines) carries scheduling, gates,
  reliability, compensation and replanning. Cohesive but large; splitting by
  concern is the right next refactor (recorded in the summary as debt).
- The optional Dockerfile from AMB-12 was not produced; harmless for the
  assessment (no external services) but it is a stated option left undone.

## Orchestration Concerns

- Gate timeouts are evaluated on the next `run`/`resume` call, not by a
  background timer. Correct for the demonstrated semantics, but a reviewer
  should know a waiting run will not safe-stop on its own.
- Parallelism is a per-batch thread pool; a long stage in one batch delays
  the next batch's ready set (batch-synchronous scheduling). Acceptable for
  the prototype; noted.

## Governance Concerns

- None blocking. The scripted decisions in committed evidence are disclosed in
  all three walkthroughs and the testing doc; the interactive path is
  provided and was exercised in this review.

## Testing Concerns

- The redirect p95 benchmark runs in the suite with a local threshold; it is
  labelled demo-only but could be flaky on a slow CI runner (marked `slow`).
- No mutation or fuzz testing of the state machine beyond the parametrised
  transition table.

## Security and Reliability Concerns

- DNS-resolving SSRF check remains deferred (AMB-03) — `127.0.0.1.nip.io` is
  accepted by design and recorded as a production recommendation.
- Rate limiting is per API key and per process.
- Analytics are best-effort (loss on crash) by decision AMB-05.

## Documentation and Traceability Concerns

- Test counts appear in several documents; they were refreshed to 298 after
  the review fixes. A generated badge or a single source would avoid drift.

## Git History Assessment

Nearly sixty coherent conventional commits from SpecKit init through governance
artifacts, test→feat pairs for every behaviour group, scenario evidence
commits, documentation, then review-driven fixes with their own red commits.
Timestamps reflect the actual working sessions. No history rewriting after
the initial push beyond the first three commits' trailers.

## Likely Reviewer Questions

1. Why a hand-built scheduler instead of LangGraph/Temporal? (ADR-005)
2. How do you know the gate cannot be bypassed? (ADR-007; forged-row test; `decide` is the only path)
3. What is the difference between rollback and compensation in your system, and when is each used? (ADR-008; workspace inverse ops vs `compensate()`)
4. Walk through the replan: what is invalidated and why are gates re-decided? (ADR-009; `replans.json`)
5. Why deterministic agents, and what changes with an LLM behind the protocol? (ADR-010; artifact schemas as the contract)
6. How is MTTR computed and what is excluded? (`metrics.py`; unrecovered excluded)
7. What would it take to run two workers? (lease column + store-backed queue; §8 architecture)
8. Why SQLite, and how would you migrate? (ADR-003; ports + Alembic)
9. What did the review find and how did you fix it? (this document)
10. What would you cut or add with one more day? (BACKLOG; engine split; DNS check)

## Prioritized Remediation Plan

| # | Item | Where | Effort | Status |
|---|---|---|---|---|
| 1 | Reject abbreviated numeric hosts; strip trailing dot | `domain/validation.py` | S | done (`f597286`) |
| 2 | Per-run lock on run-moving operations | `orchestration/engine.py` | S | done (`16e7f5d`) |
| 3 | Correct documentation drift (field names, status codes, CLI names, counts) | `docs/`, `quickstart.md` | S | done |
| 4 | Split `engine.py` into scheduler / gates / reliability / replanning modules | `orchestration/` | M | deferred (debt) |
| 5 | Stage lease column + store-backed queue for multi-process execution | `persistence/tables.py`, `engine.py` | M | backlog |
| 6 | DNS-resolving SSRF check with negative cache | `domain/validation.py` | M | backlog (AMB-03) |
| 7 | Background gate-timeout ticker | `cli.py serve` | S | backlog |
| 8 | Single source for test counts in docs | `scripts/` | S | backlog |
