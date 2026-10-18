"""ShortenerService — the application-plane use cases.

Everything here is deterministic given the injected clock and repositories,
which is what makes the behaviour unit-testable without a database.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from agentic_sdlc.domain.codes import generate_code
from agentic_sdlc.domain.models import AnalyticsSummary, RedirectEvent, ShortLink
from agentic_sdlc.domain.ports import AnalyticsRepository, ShortLinkRepository
from agentic_sdlc.domain.validation import UrlPolicy, validate_target_url
from agentic_sdlc.errors import (
    ConflictError,
    GoneError,
    NotFoundError,
    StoreUnavailableError,
    ValidationError,
)

Clock = Callable[[], datetime]

_BOT_MARKERS = ("bot", "crawler", "spider", "slurp", "facebookexternalhit", "preview")
_BROWSER_MARKERS = ("mozilla/", "chrome/", "safari/", "firefox/", "edg/")


def classify_user_agent(user_agent: str | None) -> str:
    if not user_agent:
        return "other"
    ua = user_agent.lower()
    if any(m in ua for m in _BOT_MARKERS):
        return "bot"
    if any(m in ua for m in _BROWSER_MARKERS):
        return "browser"
    return "other"


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class CreateLinkCommand:
    target_url: str
    expires_at: datetime | None = None
    idempotency_key: str | None = None

    def payload_hash(self, normalised_url: str) -> str:
        canonical = json.dumps(
            {
                "target_url": normalised_url,
                "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            },
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()


class ShortenerService:
    def __init__(
        self,
        *,
        links: ShortLinkRepository,
        analytics: AnalyticsRepository,
        url_policy: UrlPolicy,
        code_length: int = 7,
        max_code_attempts: int = 5,
        clock: Clock = _utcnow,
        on_analytics_error: Callable[[Exception], None] | None = None,
    ) -> None:
        self._links = links
        self._analytics = analytics
        self._policy = url_policy
        self._code_length = code_length
        self._max_attempts = max_code_attempts
        self._clock = clock
        self._on_analytics_error = on_analytics_error

    # --- FR-U01, U02, U04, U06, U09, U11 ------------------------------------

    def create(self, cmd: CreateLinkCommand) -> ShortLink:
        now = self._clock()
        target = validate_target_url(cmd.target_url, self._policy)
        if cmd.expires_at is not None and cmd.expires_at <= now:
            raise ValidationError("expires_at must be in the future", field="expires_at")

        payload_hash = cmd.payload_hash(target)
        if cmd.idempotency_key:
            existing = self._links.get_by_idempotency_key(cmd.idempotency_key)
            if existing is not None:
                if existing.payload_hash == payload_hash:
                    return existing
                raise ConflictError(
                    "idempotency_key was already used with a different payload",
                    field="idempotency_key",
                )

        last_error: ConflictError | None = None
        for _ in range(self._max_attempts):
            link = ShortLink(
                code=generate_code(self._code_length),
                target_url=target,
                created_at=now,
                expires_at=cmd.expires_at,
                idempotency_key=cmd.idempotency_key,
                payload_hash=payload_hash,
            )
            try:
                return self._links.insert(link)
            except ConflictError as exc:
                # A duplicate *key* can only happen on a race between two identical
                # idempotent requests; re-read and return the winner.
                if cmd.idempotency_key:
                    winner = self._links.get_by_idempotency_key(cmd.idempotency_key)
                    if winner is not None:
                        return winner
                last_error = exc
        raise StoreUnavailableError(
            f"could not allocate a unique short code in {self._max_attempts} attempts"
        ) from last_error

    # --- FR-U05, U06, U07 ---------------------------------------------------

    def resolve(
        self, code: str, *, referrer: str | None = None, user_agent: str | None = None
    ) -> str:
        link = self._links.get_by_code(code)
        if link is None:
            raise NotFoundError("short code not found")
        now = self._clock()
        if link.is_expired(now):
            raise GoneError("short link has expired")
        event = RedirectEvent(
            code=code, occurred_at=now, referrer=referrer, ua_class=classify_user_agent(user_agent)
        )
        try:
            self._analytics.record(event)
        except Exception as exc:  # analytics must never break a redirect (AMB-05)
            if self._on_analytics_error:
                self._on_analytics_error(exc)
        return link.target_url

    # --- FR-U08 -------------------------------------------------------------

    def analytics(self, code: str) -> AnalyticsSummary:
        if self._links.get_by_code(code) is None:
            raise NotFoundError("short code not found")
        total, first, last, per_day = self._analytics.summary(code)
        return AnalyticsSummary(
            code=code,
            total_redirects=total,
            first_redirect_at=first,
            last_redirect_at=last,
            redirects_by_day=dict(sorted(per_day.items())),
        )

    def get(self, code: str) -> ShortLink:
        link = self._links.get_by_code(code)
        if link is None:
            raise NotFoundError("short code not found")
        return link
