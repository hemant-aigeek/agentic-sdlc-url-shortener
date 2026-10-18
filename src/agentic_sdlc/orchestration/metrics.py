"""Reliability and orchestration metrics derived from the event log (FR-O19).

Nothing here is sampled or estimated: every number is a count or a
difference of recorded timestamps. MTTR follows the plan's definition —
total recovery duration across *recovered* failure events divided by the
number of recovered failure events; unrecovered failures are reported
separately and never enter the denominator. All outputs are labelled as
demonstration measurements (constitution IX).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from agentic_sdlc.orchestration.events import AuditEvent, EventKind

MEASUREMENT_NOTE = (
    "Demonstration measurement from a local single-process run with deterministic agents "
    "and injected faults; not production statistics."
)

_TERMINAL = {
    EventKind.RUN_COMPLETED: "COMPLETED",
    EventKind.RUN_FAILED: "FAILED",
    EventKind.RUN_REJECTED: "REJECTED",
    EventKind.SAFE_STOP: "SAFE_STOPPED",
}


def compute_run_metrics(events: Iterable[AuditEvent]) -> dict[str, Any]:
    evs = sorted(events, key=lambda e: e.seq)
    counts = {k: 0 for k in EventKind}
    for e in evs:
        counts[e.kind] += 1

    # --- stage outcomes (final state per stage) -------------------------------
    final: dict[str, str] = {}
    for e in evs:
        if e.stage is None:
            continue
        if e.kind is EventKind.STAGE_SUCCEEDED:
            final[e.stage] = "SUCCEEDED"
        elif e.kind is EventKind.STAGE_FAILED:
            final[e.stage] = "FAILED"
        elif e.kind is EventKind.FALLBACK_USED:
            final[e.stage] = "FALLBACK"
        elif e.kind is EventKind.STAGE_SKIPPED:
            final[e.stage] = "SKIPPED"
        elif e.kind in {EventKind.COMPENSATION_COMPLETED, EventKind.ROLLBACK_COMPLETED}:
            final[e.stage] = "COMPENSATED"
        elif e.kind is EventKind.DECISION_RECORDED:
            final[e.stage] = "SUCCEEDED" if e.result in {"approve", "clarify"} else "FAILED"
    succeeded = sum(1 for s in final.values() if s == "SUCCEEDED")
    fallback = sum(1 for s in final.values() if s == "FALLBACK")
    failed = sum(1 for s in final.values() if s == "FAILED")
    decided = succeeded + fallback + failed

    # --- recovery / MTTR --------------------------------------------------------
    detected: dict[str, AuditEvent] = {}
    durations: dict[str, float] = {}
    mechanisms: dict[str, int] = {}
    for e in evs:
        if e.stage is None:
            continue
        if e.kind is EventKind.FAILURE_DETECTED and e.stage not in durations:
            detected.setdefault(e.stage, e)
        elif e.kind is EventKind.RECOVERY_COMPLETED and e.stage in detected:
            start = detected.pop(e.stage)
            durations[e.stage] = (e.at - start.at).total_seconds()
            mech = str(e.data.get("mechanism", "unknown"))
            mechanisms[mech] = mechanisms.get(mech, 0) + 1
    unrecovered = sorted(detected)
    total_recovery = sum(durations.values())
    mttr = total_recovery / len(durations) if durations else None

    # --- latency ------------------------------------------------------------------
    created = next((e for e in evs if e.kind is EventKind.RUN_CREATED), None)
    terminal = next((e for e in reversed(evs) if e.kind in _TERMINAL), None)
    e2e = (terminal.at - created.at).total_seconds() if created and terminal else None
    human_wait = 0.0
    open_gates: dict[str, AuditEvent] = {}
    for e in evs:
        if e.kind is EventKind.GATE_OPENED and e.stage:
            open_gates[e.stage] = e
        elif e.kind is EventKind.DECISION_RECORDED and e.stage in open_gates:
            human_wait += (e.at - open_gates.pop(e.stage).at).total_seconds()
    active = (e2e - human_wait) if e2e is not None else None

    return {
        "measurement_type": "demonstration",
        "measurement_note": MEASUREMENT_NOTE,
        "events": len(evs),
        "stages": {
            "started": len({e.stage for e in evs if e.kind is EventKind.STAGE_STARTED}),
            "succeeded": succeeded,
            "fallback": fallback,
            "failed": failed,
            "skipped": sum(1 for s in final.values() if s == "SKIPPED"),
            "compensated": sum(1 for s in final.values() if s == "COMPENSATED"),
            "success_rate": (succeeded / decided) if decided else None,
            "failure_rate": (failed / decided) if decided else None,
        },
        "retries": {
            "count": counts[EventKind.RETRY_SCHEDULED],
            "timeouts": counts[EventKind.STAGE_TIMED_OUT],
            "frequency_per_stage": (
                counts[EventKind.RETRY_SCHEDULED] / decided if decided else None
            ),
        },
        "fallbacks": counts[EventKind.FALLBACK_USED],
        "compensations": counts[EventKind.COMPENSATION_COMPLETED]
        + counts[EventKind.ROLLBACK_COMPLETED],
        "rollbacks": counts[EventKind.ROLLBACK_COMPLETED],
        "safe_stops": counts[EventKind.SAFE_STOP],
        "replans": counts[EventKind.REPLAN],
        "decisions": counts[EventKind.DECISION_RECORDED],
        "recovery": {
            "definition": (
                "MTTR = total recovery duration across recovered failure events / "
                "number of recovered failure events; unrecovered failures are excluded "
                "from the denominator"
            ),
            "population": "stages with a failure_detected event in this run",
            "recovered_failures": len(durations),
            "unrecovered_failures": len(unrecovered),
            "unrecovered": unrecovered,
            "recovery_durations_s": durations,
            "total_recovery_duration_s": total_recovery,
            "mttr_s": mttr,
            "mechanisms": mechanisms,
            "timestamps": (
                "failure_detected -> recovery_completed (recovery_started recorded per attempt)"
            ),
        },
        "latency": {
            "end_to_end_s": e2e,
            "human_wait_s": human_wait,
            "active_s": active,
            "terminal_state": _TERMINAL[terminal.kind] if terminal else None,
        },
    }


def aggregate(run_metrics: Iterable[dict[str, Any]]) -> dict[str, Any]:
    runs = list(run_metrics)
    terminal: dict[str, int] = {}
    recovered = unrecovered = 0
    total_recovery = 0.0
    retries = fallbacks = compensations = safe_stops = replans = 0
    latencies: list[float] = []
    for m in runs:
        state = m["latency"]["terminal_state"]
        if state:
            terminal[state] = terminal.get(state, 0) + 1
        recovered += m["recovery"]["recovered_failures"]
        unrecovered += m["recovery"]["unrecovered_failures"]
        total_recovery += m["recovery"]["total_recovery_duration_s"]
        retries += m["retries"]["count"]
        fallbacks += m["fallbacks"]
        compensations += m["compensations"]
        safe_stops += m["safe_stops"]
        replans += m["replans"]
        if m["latency"]["end_to_end_s"] is not None:
            latencies.append(m["latency"]["end_to_end_s"])
    finished = sum(terminal.values())
    return {
        "measurement_type": "demonstration",
        "measurement_note": MEASUREMENT_NOTE,
        "runs": len(runs),
        "terminal_states": terminal,
        "workflow_success_rate": (terminal.get("COMPLETED", 0) / finished) if finished else None,
        "workflow_failure_rate": (
            (finished - terminal.get("COMPLETED", 0)) / finished if finished else None
        ),
        "retries": retries,
        "fallbacks": fallbacks,
        "compensations": compensations,
        "safe_stops": safe_stops,
        "replans": replans,
        "recovery": {
            "recovered_failures": recovered,
            "unrecovered_failures": unrecovered,
            "total_recovery_duration_s": total_recovery,
            "mttr_s": (total_recovery / recovered) if recovered else None,
        },
        "latency": {
            "mean_end_to_end_s": (sum(latencies) / len(latencies)) if latencies else None,
            "max_end_to_end_s": max(latencies) if latencies else None,
        },
    }
