# Gate 3 — Clarification Decisions

- **Artifact**: spec §9 (ambiguities) and §10 (assumptions)
- **Decider**: Hemant Gupta
- **Date**: 2026-10-18
- **Decision**: all twelve ambiguities resolved as recorded below; assumptions
  AS-01..AS-05 approved as proposed validation targets (not client requirements).

| ID | Decision | Rationale (candidate's) |
|---|---|---|
| AMB-01 | New short code per create request; explicit dedupe only via idempotency key | Keeps create semantics simple and supports per-campaign links; dedupe-by-URL is an easy later index if needed |
| AMB-02 | 7-character random base62 code | Large keyspace, URL-safe, not guessable from sequence or target |
| AMB-03 | Literal IP range checks + hostname block-list at creation; DNS-resolution check recorded as production recommendation | Avoids a network dependency in tests; the residual risk is disclosed, not hidden |
| AMB-04 | No default expiry; optional `expires_at` | The assignment does not mandate a default; forcing one would be a silent product decision |
| AMB-05 | Best-effort in-process analytics write; redirect path never blocks on it; loss-on-crash is a documented limitation | Redirect latency and availability outrank analytics completeness for a shortener |
| AMB-06 | Static API key for mutating/approval endpoints; actor identity from a request header | Approvals need an actor; a full identity provider is out of scope and would add nothing to the assessment |
| AMB-07 | Minimal in-process token-bucket limiter on creation; production placement documented | Demonstrates the control without pretending to be a gateway |
| AMB-08 | Agents are deterministic stage executors behind an `Agent` protocol; an LLM-backed adapter is backlog | Reproducible scenarios a reviewer can rerun offline matter more than non-deterministic flair |
| AMB-09 | Gate timeout configurable per gate; none in interactive use; tests prove timeout → SAFE_STOPPED | Silence must never approve; timeout must never advance |
| AMB-10 | Rollback for reversible store writes; compensation (recorded inverse action) otherwise | Matches constitution VIII; keeps the distinction demonstrable |
| AMB-11 | Audit retained for the life of the local store; retention policy documented as config | No retention requirement was given |
| AMB-12 | Local process + optional Dockerfile; no cloud | Assignment asks for a locally runnable prototype |

## Technology decision (recorded here, formalised in ADRs)
Python 3.12+, FastAPI, SQLite via SQLAlchemy, pytest. Chosen by the candidate
for fastest path to a demonstrable, single-process, locally runnable system with
no infrastructure to explain.
