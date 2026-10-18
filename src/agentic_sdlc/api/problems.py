"""RFC 9457 problem+json responses (FR-U13).

Every error leaving the API has the same shape and never contains a stack
trace. ``instance`` carries the request correlation ID so a client report can
be matched to logs.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from agentic_sdlc.errors import AgenticError, ValidationError
from agentic_sdlc.telemetry.logging import get_logger

PROBLEM_TYPE_BASE = "https://agentic-sdlc.local/problems/"
MEDIA_TYPE = "application/problem+json"
log = get_logger(__name__)


def problem(
    request: Request,
    *,
    status: int,
    title: str,
    detail: str,
    type_slug: str,
    **extra: Any,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": PROBLEM_TYPE_BASE + type_slug,
        "title": title,
        "status": status,
        "detail": detail,
        "instance": getattr(request.state, "correlation_id", "unknown"),
    }
    body.update({k: v for k, v in extra.items() if v is not None})
    headers = {"Retry-After": str(extra["retry_after"])} if "retry_after" in extra else None
    return JSONResponse(body, status_code=status, media_type=MEDIA_TYPE, headers=headers)


def install_problem_handlers(app: FastAPI) -> None:
    @app.exception_handler(AgenticError)
    async def _agentic(request: Request, exc: AgenticError) -> JSONResponse:
        extra: dict[str, Any] = dict(exc.extra)
        if isinstance(exc, ValidationError) and exc.field:
            extra["errors"] = [{"field": exc.field, "message": exc.detail}]
        return problem(
            request,
            status=exc.status_code,
            title=exc.title,
            detail=exc.detail,
            type_slug=type(exc).__name__.removesuffix("Error").lower(),
            **extra,
        )

    @app.exception_handler(RequestValidationError)
    async def _request_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {
                "field": ".".join(str(p) for p in e.get("loc", ()) if p != "body"),
                "message": e.get("msg", ""),
            }
            for e in exc.errors()
        ]
        return problem(
            request,
            status=422,
            title="Validation failed",
            detail="request body or parameters are invalid",
            type_slug="validation",
            errors=errors,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return problem(
            request,
            status=exc.status_code,
            title={404: "Not found", 405: "Method not allowed"}.get(exc.status_code, "Error"),
            detail=str(exc.detail),
            type_slug=f"http-{exc.status_code}",
        )

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        # Logged with the correlation id; the client gets no internals.
        log.error("unhandled_exception", error_type=type(exc).__name__)
        return problem(
            request,
            status=500,
            title="Internal error",
            detail="an unexpected error occurred",
            type_slug="internal",
        )
