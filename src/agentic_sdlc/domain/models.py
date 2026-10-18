"""Application-plane domain models. Plain, immutable, no I/O."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class ShortLink:
    code: str
    target_url: str
    created_at: datetime
    expires_at: datetime | None = None
    idempotency_key: str | None = None
    payload_hash: str | None = None

    def is_expired(self, now: datetime) -> bool:
        return self.expires_at is not None and now >= self.expires_at


@dataclass(frozen=True)
class RedirectEvent:
    code: str
    occurred_at: datetime
    referrer: str | None
    ua_class: str


@dataclass(frozen=True)
class AnalyticsSummary:
    code: str
    total_redirects: int
    first_redirect_at: datetime | None
    last_redirect_at: datetime | None
    redirects_by_day: dict[str, int] = field(default_factory=dict)
