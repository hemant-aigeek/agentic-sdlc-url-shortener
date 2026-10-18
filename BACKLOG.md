# Backlog — deferred scope

Items here were consciously excluded from the 2–3 day assessment timebox
(plan §12, task TB-01). None of them is required to demonstrate the
orchestration, governance, reliability or evidence requirements. Each entry
states why it was deferred and what it would take.

| Item | Why deferred | What it would take |
|---|---|---|
| LLM-backed agent adapter | Non-deterministic scenarios would not be reproducible by a reviewer offline; the `Agent` protocol is the extension point (ADR-010) | An adapter implementing `Agent.execute` that prompts a model with the stage context and validates the structured output against the artifact schema |
| DNS-resolving SSRF check | Adds a network dependency to creation and to tests (AMB-03) | Resolve host at creation, apply the same range rules to every A/AAAA answer, cache negative results, time-box the lookup |
| Dedupe-by-target-URL index | Not required; idempotency keys cover explicit dedupe (AMB-01) | Unique index on a normalised-URL hash and a `return_existing` create option |
| Postgres store | SQLite is sufficient for a single-process prototype (ADR-003) | Alembic migrations, connection pooling config, the same repository interfaces |
| Async analytics queue | In-process best-effort recorder is enough for the demo (AMB-05) | Outbox table + worker, or a broker; at-least-once semantics documented |
| OpenTelemetry export | Correlation IDs and event log already allow reconstruction | OTLP exporter, span per stage attempt |
| Docker Compose | Single process, no services; a plain Dockerfile is optional | Compose file with volume for `data/` |
| Rate limiting at the gateway | In-process token bucket demonstrates the control (AMB-07) | Move to reverse proxy / API gateway in deployment |
| Vanity / custom short codes | Out of scope (EX-01) | Validation rules, reserved-word list, collision semantics |
