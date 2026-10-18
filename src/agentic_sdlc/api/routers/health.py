"""Liveness and readiness (FR-U12).

Liveness answers "is the process up"; readiness answers "can it serve", which
for this system means the persistence dependency responds.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

from agentic_sdlc.api.problems import MEDIA_TYPE, PROBLEM_TYPE_BASE
from agentic_sdlc.persistence.db import Database

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready(request: Request) -> JSONResponse:
    db: Database = request.app.state.db
    database_ok = db.ping()
    checks = {"database": "ok" if database_ok else "fail"}
    if database_ok:
        return JSONResponse({"status": "ok", "checks": checks})
    return JSONResponse(
        {
            "type": PROBLEM_TYPE_BASE + "not-ready",
            "title": "Service not ready",
            "status": 503,
            "detail": "a required dependency is unavailable",
            "instance": getattr(request.state, "correlation_id", "unknown"),
            "status_text": "fail",
            "checks": checks,
        },
        status_code=503,
        media_type=MEDIA_TYPE,
    )
