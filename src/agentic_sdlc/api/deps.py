"""Dependency wiring for request handlers.

Services are built per request from ``app.state`` so tests can swap the
database or settings on a live app without re-creating the router tree.
"""

from __future__ import annotations

from fastapi import Request

from agentic_sdlc.api.ratelimit import TokenBucketLimiter
from agentic_sdlc.config import Settings
from agentic_sdlc.domain.service import ShortenerService
from agentic_sdlc.domain.validation import UrlPolicy
from agentic_sdlc.persistence.db import Database
from agentic_sdlc.persistence.link_repository import (
    SqlAnalyticsRepository,
    SqlShortLinkRepository,
)
from agentic_sdlc.telemetry.logging import get_logger

log = get_logger(__name__)


def get_db(request: Request) -> Database:
    return request.app.state.db  # type: ignore[no-any-return]


def get_limiter(request: Request) -> TokenBucketLimiter:
    return request.app.state.limiter  # type: ignore[no-any-return]


def get_shortener(request: Request) -> ShortenerService:
    settings: Settings = request.app.state.settings
    db: Database = request.app.state.db
    return ShortenerService(
        links=SqlShortLinkRepository(db),
        analytics=SqlAnalyticsRepository(db),
        url_policy=UrlPolicy(
            max_length=settings.max_url_length,
            blocked_hostnames=settings.blocked_hostnames,
            blocked_hostname_suffixes=settings.blocked_hostname_suffixes,
        ),
        code_length=settings.short_code_length,
        max_code_attempts=settings.short_code_max_attempts,
        on_analytics_error=lambda exc: log.warning(
            "analytics_record_failed", error_type=type(exc).__name__
        ),
    )
