# ADR-008: Per-stage retry/timeout/fallback; safe-stop terminal; rollback-vs-compensation rule

## Status
Proposed (Gate 4 pending) — resolves AMB-10, AS-01.

## Context
FR-O08..O13 and constitution VIII require bounded retries, timeouts,
fallback, a distinction between rollback and compensation, deterministic
safe-stop, and resume.

## Decision
- `FailureKind = TRANSIENT | PERMANENT`; agents raise `StageError(kind)`;
  timeouts are TRANSIENT; unknown exceptions are PERMANENT.
- `RetryPolicy(max_attempts=3, base_delay=0.1, multiplier=2, max_delay=2)` default (AS-01); tests shrink delays.
- `TimeoutPolicy(seconds)` per attempt, enforced with future timeout; `verify` passes it to the subprocess.
- Fallback: optional agent run after exhaustion; stage ends `FALLBACK`; downstream may proceed only if the stage declares `fallback_satisfies_exit=True`.
- Safe-stop triggers: exhaustion with no fallback; gate timeout; mandatory policy FAIL without approved exception; illegal transition; operator stop. Terminal, reason recorded, workspace left intact for inspection.
- **Rollback** = restoring prior state via recorded inverse operations (workspace file ops). **Compensation** = executing a registered counteracting action when inversion is impossible (e.g. a notification already emitted). On rejection, side-effecting stages are compensated in reverse topological order; each outcome is an event.
- Resume: on load, stages found `RUNNING` are treated as interrupted (`RETRYING` if eligible, else `FAILED`).

## Options Considered
Global retry wrapper (rejected: hides policy per stage); unlimited retries
with jitter (rejected: violates bounded retry); treating rollback and
compensation as one "undo" (rejected: constitution VIII).

## Consequences
- Testing: one test per mechanism plus combined paths.
- Metrics: `failure_detected` → `recovery_completed` events feed MTTR.

## Risks and Mitigations
- Compensation itself failing → recorded `compensation_failed`, run `FAILED` with reason; never silently COMPENSATED.

## Reversibility
Easy; policies are data on `StageSpec`.

## Traceability
FR-O08..O13, NFR-02, NFR-03, AS-01.

## Validation
`tests/orchestration/test_retry.py`, `test_timeout.py`, `test_fallback.py`,
`test_compensation.py`, `test_safe_stop.py`, `test_resume.py`; demo exports.
