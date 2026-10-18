"""SQLite implementations of the application-plane ports (ADR-003).

Datetimes are stored as UTC and re-attached with ``tzinfo=UTC`` on read, since
SQLite has no timezone-aware type.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, insert, select
from sqlalchemy.engine import Row
from sqlalchemy.exc import IntegrityError

from agentic_sdlc.domain.models import RedirectEvent, ShortLink
from agentic_sdlc.domain.ports import AnalyticsRepository, ShortLinkRepository
from agentic_sdlc.errors import ConflictError
from agentic_sdlc.persistence.db import Database
from agentic_sdlc.persistence.tables import redirect_events, short_links


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _row_to_link(row: Row[tuple[object, ...]]) -> ShortLink:
    m = row._mapping
    created = _aware(m["created_at"])
    assert created is not None
    return ShortLink(
        code=m["code"],
        target_url=m["target_url"],
        created_at=created,
        expires_at=_aware(m["expires_at"]),
        idempotency_key=m["idempotency_key"],
        payload_hash=m["payload_hash"],
    )


class SqlShortLinkRepository(ShortLinkRepository):
    def __init__(self, db: Database) -> None:
        self._db = db

    def insert(self, link: ShortLink) -> ShortLink:
        try:
            with self._db.begin() as conn:
                conn.execute(
                    insert(short_links).values(
                        code=link.code,
                        target_url=link.target_url,
                        created_at=link.created_at,
                        expires_at=link.expires_at,
                        idempotency_key=link.idempotency_key,
                        payload_hash=link.payload_hash,
                    )
                )
        except IntegrityError as exc:
            raise ConflictError("short link with this code or idempotency key exists") from exc
        return link

    def get_by_code(self, code: str) -> ShortLink | None:
        with self._db.connect() as conn:
            row = conn.execute(select(short_links).where(short_links.c.code == code)).first()
        return _row_to_link(row) if row is not None else None

    def get_by_idempotency_key(self, key: str) -> ShortLink | None:
        with self._db.connect() as conn:
            row = conn.execute(
                select(short_links).where(short_links.c.idempotency_key == key)
            ).first()
        return _row_to_link(row) if row is not None else None


class SqlAnalyticsRepository(AnalyticsRepository):
    def __init__(self, db: Database) -> None:
        self._db = db

    def record(self, event: RedirectEvent) -> None:
        with self._db.begin() as conn:
            conn.execute(
                insert(redirect_events).values(
                    code=event.code,
                    occurred_at=event.occurred_at,
                    referrer=event.referrer,
                    ua_class=event.ua_class,
                )
            )

    def summary(self, code: str) -> tuple[int, datetime | None, datetime | None, dict[str, int]]:
        with self._db.connect() as conn:
            agg = conn.execute(
                select(
                    func.count(redirect_events.c.id),
                    func.min(redirect_events.c.occurred_at),
                    func.max(redirect_events.c.occurred_at),
                ).where(redirect_events.c.code == code)
            ).one()
            day = func.substr(redirect_events.c.occurred_at, 1, 10)
            per_day_rows = conn.execute(
                select(day, func.count(redirect_events.c.id))
                .where(redirect_events.c.code == code)
                .group_by(day)
                .order_by(day)
            ).all()
        total = int(agg[0] or 0)
        if total == 0:
            return 0, None, None, {}
        first = _aware(datetime.fromisoformat(str(agg[1])))
        last = _aware(datetime.fromisoformat(str(agg[2])))
        return total, first, last, {str(d): int(n) for d, n in per_day_rows}
