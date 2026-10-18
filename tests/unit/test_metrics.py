"""FR-O19 / plan §5: reliability and orchestration metrics are computed from the event log."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from agentic_sdlc.orchestration.events import ActorType, AuditEvent, EventKind
from agentic_sdlc.orchestration.metrics import aggregate, compute_run_metrics

pytestmark = pytest.mark.unit

T0 = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


def ev(
    seq: int, kind: EventKind, secs: float, stage: str | None = None, **data: object
) -> AuditEvent:
    return AuditEvent(
        run_id="r",
        seq=seq,
        kind=kind,
        actor_type=ActorType.SYSTEM,
        at=T0 + timedelta(seconds=secs),
        stage=stage,
        result=str(data.pop("result", "")) or None,
        data=dict(data),
    )


def scripted_run() -> list[AuditEvent]:
    return [
        ev(1, EventKind.RUN_CREATED, 0),
        ev(2, EventKind.STAGE_STARTED, 1, "a"),
        ev(3, EventKind.STAGE_SUCCEEDED, 2, "a", result="SUCCEEDED"),
        ev(4, EventKind.STAGE_STARTED, 2, "b"),
        ev(5, EventKind.FAILURE_DETECTED, 3, "b"),
        ev(6, EventKind.RETRY_SCHEDULED, 3, "b"),
        ev(7, EventKind.RECOVERY_STARTED, 3, "b", mechanism="retry"),
        ev(8, EventKind.STAGE_STARTED, 4, "b"),
        ev(9, EventKind.STAGE_SUCCEEDED, 7, "b", result="SUCCEEDED"),
        ev(
            10, EventKind.RECOVERY_COMPLETED, 7, "b", mechanism="retry"
        ),  # recovery took 4s (3 -> 7)
        ev(11, EventKind.STAGE_STARTED, 7, "c"),
        ev(12, EventKind.FAILURE_DETECTED, 8, "c"),
        ev(13, EventKind.STAGE_TIMED_OUT, 8, "c"),
        ev(14, EventKind.STAGE_FAILED, 8, "c", result="FAILED"),
        ev(15, EventKind.RECOVERY_STARTED, 8, "c", mechanism="fallback"),
        ev(16, EventKind.FALLBACK_USED, 10, "c", result="FALLBACK"),
        ev(17, EventKind.RECOVERY_COMPLETED, 10, "c", mechanism="fallback"),  # 2s (8 -> 10)
        ev(18, EventKind.GATE_OPENED, 10, "approve"),
        ev(19, EventKind.DECISION_RECORDED, 70, "approve", result="approve"),  # human waited 60s
        ev(20, EventKind.STAGE_STARTED, 70, "d"),
        ev(21, EventKind.FAILURE_DETECTED, 71, "d"),
        ev(22, EventKind.STAGE_FAILED, 71, "d", result="FAILED"),  # never recovered
        ev(23, EventKind.SAFE_STOP, 71, None, result="SAFE_STOPPED"),
    ]


@pytest.mark.req("FR-O19")
def test_counts_and_rates() -> None:
    m = compute_run_metrics(scripted_run())
    assert (
        m["stages"]["succeeded"] == 3  # a, b and the approved gate
        and m["stages"]["fallback"] == 1
        and m["stages"]["failed"] == 1
    )
    assert m["stages"]["success_rate"] == pytest.approx(3 / 5)
    assert m["stages"]["failure_rate"] == pytest.approx(1 / 5)
    assert m["retries"]["count"] == 1 and m["retries"]["timeouts"] == 1
    assert m["fallbacks"] == 1 and m["safe_stops"] == 1 and m["compensations"] == 0


@pytest.mark.req("FR-O19")
def test_mttr_uses_recovered_failures_only_and_reports_unrecovered_separately() -> None:
    m = compute_run_metrics(scripted_run())
    r = m["recovery"]
    assert r["recovered_failures"] == 2
    assert r["unrecovered_failures"] == 1
    assert r["recovery_durations_s"] == {"b": 4.0, "c": 2.0}
    assert r["total_recovery_duration_s"] == 6.0
    assert r["mttr_s"] == pytest.approx(3.0)  # (4 + 2) / 2, NOT / 3
    assert r["mechanisms"] == {"retry": 1, "fallback": 1}
    assert r["unrecovered"] == ["d"]


@pytest.mark.req("FR-O19")
def test_mttr_is_none_without_recovered_failures() -> None:
    m = compute_run_metrics(
        [ev(1, EventKind.RUN_CREATED, 0), ev(2, EventKind.STAGE_STARTED, 1, "a")]
    )
    assert m["recovery"]["mttr_s"] is None and m["recovery"]["recovered_failures"] == 0


@pytest.mark.req("FR-O19")
def test_latency_separates_human_wait_from_active_time() -> None:
    m = compute_run_metrics(scripted_run())
    lat = m["latency"]
    assert lat["end_to_end_s"] == 71.0
    assert lat["human_wait_s"] == 60.0
    assert lat["active_s"] == 11.0
    assert lat["terminal_state"] == "SAFE_STOPPED"


@pytest.mark.req("FR-O19")
def test_in_progress_run_has_no_end_to_end_latency() -> None:
    m = compute_run_metrics(scripted_run()[:18])
    assert m["latency"]["end_to_end_s"] is None and m["latency"]["terminal_state"] is None


@pytest.mark.req("FR-O19")
def test_measurements_are_labelled_demonstration_data() -> None:
    m = compute_run_metrics(scripted_run())
    assert m["measurement_type"] == "demonstration"
    assert "not production" in m["measurement_note"]


@pytest.mark.req("FR-O19")
def test_aggregate_across_runs() -> None:
    a = compute_run_metrics(scripted_run())
    b = compute_run_metrics(
        [ev(1, EventKind.RUN_CREATED, 0), ev(2, EventKind.RUN_COMPLETED, 5, result="COMPLETED")]
    )
    agg = aggregate([a, b])
    assert agg["runs"] == 2
    assert agg["terminal_states"] == {"SAFE_STOPPED": 1, "COMPLETED": 1}
    assert agg["workflow_success_rate"] == pytest.approx(0.5)
    assert (
        agg["recovery"]["recovered_failures"] == 2 and agg["recovery"]["unrecovered_failures"] == 1
    )
    assert agg["recovery"]["mttr_s"] == pytest.approx(3.0)
    assert agg["measurement_type"] == "demonstration"
