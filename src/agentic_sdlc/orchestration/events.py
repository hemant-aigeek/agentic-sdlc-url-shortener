"""Audit events (FR-O20, NFR-04, NFR-05; constitution IX).

The event log is append-only and is the system of record for reconstructing
a run. Every event carries actor type, action, timestamp, target, result and
reason; MTTR-relevant events are explicit kinds rather than inferred.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class ActorType(StrEnum):
    AGENT = "agent"
    HUMAN = "human"
    SYSTEM = "system"


class EventKind(StrEnum):
    RUN_CREATED = "run_created"
    STAGE_READY = "stage_ready"
    STAGE_STARTED = "stage_started"
    STAGE_SUCCEEDED = "stage_succeeded"
    STAGE_FAILED = "stage_failed"
    STAGE_SKIPPED = "stage_skipped"
    FAILURE_DETECTED = "failure_detected"
    RETRY_SCHEDULED = "retry_scheduled"
    RECOVERY_STARTED = "recovery_started"
    RECOVERY_COMPLETED = "recovery_completed"
    STAGE_TIMED_OUT = "stage_timed_out"
    FALLBACK_USED = "fallback_used"
    GATE_OPENED = "gate_opened"
    DECISION_RECORDED = "decision_recorded"
    COMPENSATION_STARTED = "compensation_started"
    COMPENSATION_COMPLETED = "compensation_completed"
    ROLLBACK_COMPLETED = "rollback_completed"
    SAFE_STOP = "safe_stop"
    RUN_SUSPENDED = "run_suspended"
    RUN_RESUMED = "run_resumed"
    REPLAN = "replan"
    ARTIFACT_INVALIDATED = "artifact_invalidated"
    POLICY_EVALUATED = "policy_evaluated"
    EXCEPTION_REQUESTED = "exception_requested"
    EXCEPTION_APPROVED = "exception_approved"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    RUN_REJECTED = "run_rejected"


@dataclass(frozen=True)
class AuditEvent:
    run_id: str
    seq: int
    kind: EventKind
    actor_type: ActorType
    at: datetime
    stage: str | None = None
    attempt: int | None = None
    target: str | None = None
    result: str | None = None
    reason: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "seq": self.seq,
            "kind": self.kind.value,
            "actor_type": self.actor_type.value,
            "at": self.at.isoformat(),
            "stage": self.stage,
            "attempt": self.attempt,
            "target": self.target,
            "result": self.result,
            "reason": self.reason,
            "data": self.data,
        }
