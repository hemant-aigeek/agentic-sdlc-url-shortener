"""Exception hierarchy shared by both planes.

Application-plane errors map 1:1 onto problem+json responses (FR-U13).
Control-plane errors carry a failure *kind* so the engine can decide whether a
stage is retry-eligible (FR-O08) without inspecting messages.
"""

from __future__ import annotations

from enum import StrEnum


class AgenticError(Exception):
    """Base class; ``detail`` is safe to show to a client."""

    status_code = 500
    title = "Internal error"

    def __init__(self, detail: str = "", **extra: object) -> None:
        super().__init__(detail or self.title)
        self.detail = detail or self.title
        self.extra = extra


# --- application plane ------------------------------------------------------


class ValidationError(AgenticError):
    status_code = 422
    title = "Validation failed"

    def __init__(self, detail: str, field: str | None = None, **extra: object) -> None:
        super().__init__(detail, **extra)
        self.field = field


class NotFoundError(AgenticError):
    status_code = 404
    title = "Not found"


class GoneError(AgenticError):
    status_code = 410
    title = "Gone"


class ConflictError(AgenticError):
    status_code = 409
    title = "Conflict"


class UnauthorizedError(AgenticError):
    status_code = 401
    title = "Unauthorized"


class RateLimitedError(AgenticError):
    status_code = 429
    title = "Too many requests"


class StoreUnavailableError(AgenticError):
    status_code = 503
    title = "Persistence unavailable"


# --- control plane ----------------------------------------------------------


class FailureKind(StrEnum):
    TRANSIENT = "TRANSIENT"
    PERMANENT = "PERMANENT"


class StageError(AgenticError):
    """Raised by an agent to fail a stage with an explicit classification."""

    status_code = 500
    title = "Stage failed"

    def __init__(self, detail: str, kind: FailureKind = FailureKind.PERMANENT) -> None:
        super().__init__(detail)
        self.kind = kind


class TransientStageError(StageError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail, FailureKind.TRANSIENT)


class IllegalTransitionError(AgenticError):
    status_code = 409
    title = "Illegal state transition"


class GateRequiredError(AgenticError):
    status_code = 409
    title = "Human decision required"


class WorkflowNotFoundError(NotFoundError):
    title = "Workflow not found"
