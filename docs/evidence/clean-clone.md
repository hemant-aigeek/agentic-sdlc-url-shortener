# Clean-clone verification (NFR-12, SC-01)

Executed by the candidate on 2026-10-19 (UTC) against commit `346b084`
(`docs: add reviewer navigation guide; bring README and quickstart up to date`)
on a fresh checkout in an empty directory, with a new virtual environment.

| Item | Value |
|---|---|
| Platform | Linux 6.18 x86_64 |
| Python | 3.12.3 (`python3.12 -m venv .venv`) |
| Install | `pip install -e ".[dev]"` — exit 0, no external services |
| `./scripts/check.sh` | **ALL CHECKS PASSED** in 25.3 s wall-clock (ruff lint + format, mypy strict: *no issues in 60 source files*, pytest: **289 passed**, OpenAPI drift: none, secret scan: none, licences: 77 distributions allow-listed) |
| `agentic-sdlc serve` | started; `GET /health/live` → 200; `POST /api/v1/links` → 201 with a 7-char code |

## Scenarios replayed in the clean clone

`agentic-sdlc scenario run <name> --actor hemant --export <dir>` for each
scenario; terminal state and release decision read back from the exported
`run.json` / `scenario.json`:

| Scenario | State | Release decision | Terminal reason | Expected (from `scenario list`) |
|---|---|---|---|---|
| greenfield | COMPLETED | READY | — | COMPLETED / READY ✓ |
| brownfield | COMPLETED | READY | — | COMPLETED / READY ✓ |
| ambiguous | COMPLETED | READY WITH ACCEPTED LIMITATIONS | — | ✓ |
| policy-fail | SAFE_STOPPED | NOT READY | `POLICY_BLOCKED: mandatory policy failed with no admissible exception: SEC-002 …` | SAFE_STOPPED / NOT READY ✓ |
| rejection | REJECTED | NOT READY | `REJECTED at release_readiness: not this sprint; defer the endpoint` | REJECTED ✓ |
| resume | COMPLETED | READY | — | COMPLETED / READY ✓ |
| gate-timeout | SAFE_STOPPED | NOT READY | `GATE_TIMEOUT: design_approval received no decision within 1.0s` | SAFE_STOPPED / GATE_TIMEOUT ✓ |

Run ids and timestamps differ from the committed exports under
`docs/evidence/<scenario>/` (those are the original runs); the stage tables,
skip/retry/fallback sequences, policy outcomes and terminal states are the
same, as asserted by `tests/e2e/test_scenarios.py`.

## Notes

- The suite count was 289 at this commit; `tests/architecture/test_traceability.py`
  (which requires this file to exist) was added in the following commit,
  taking the suite to 290.
- The verification was run on Linux. The commands in `README.md` are POSIX;
  the Windows activation path is noted inline. No platform-specific code is
  used (SQLite file paths are built with `pathlib`).
