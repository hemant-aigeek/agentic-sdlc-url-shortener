"""FR-U10 / NFR-05 / ADR-003: SQLite repositories for the application plane."""

from __future__ import annotations

import tempfile
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from agentic_sdlc.domain.models import RedirectEvent, ShortLink
from agentic_sdlc.domain.service import CreateLinkCommand, ShortenerService
from agentic_sdlc.domain.validation import UrlPolicy
from agentic_sdlc.errors import ConflictError
from agentic_sdlc.persistence.db import Database
from agentic_sdlc.persistence.link_repository import (
    SqlAnalyticsRepository,
    SqlShortLinkRepository,
)

pytestmark = pytest.mark.integration

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


@pytest.fixture
def db() -> Iterator[Database]:
    # A real file so that multiple threads get independent connections.
    with tempfile.TemporaryDirectory() as tmp:
        database = Database(f"sqlite+pysqlite:///{Path(tmp) / 'links.db'}")
        database.create_all()
        yield database
        database.dispose()


@pytest.mark.req("FR-U01", "FR-U04")
def test_insert_and_get_roundtrip(db: Database) -> None:
    repo = SqlShortLinkRepository(db)
    link = ShortLink(
        code="abc1234",
        target_url="https://example.com",
        created_at=NOW,
        expires_at=NOW + timedelta(days=1),
    )
    repo.insert(link)
    got = repo.get_by_code("abc1234")
    assert got == link
    assert got is not None and got.expires_at is not None and got.expires_at.tzinfo is not None


@pytest.mark.req("FR-U04")
def test_duplicate_code_raises_conflict(db: Database) -> None:
    repo = SqlShortLinkRepository(db)
    repo.insert(ShortLink(code="dup0000", target_url="https://example.com", created_at=NOW))
    with pytest.raises(ConflictError):
        repo.insert(ShortLink(code="dup0000", target_url="https://example.org", created_at=NOW))


@pytest.mark.req("FR-U09")
def test_duplicate_idempotency_key_raises_conflict_and_is_retrievable(db: Database) -> None:
    repo = SqlShortLinkRepository(db)
    repo.insert(
        ShortLink(
            code="k000001",
            target_url="https://example.com",
            created_at=NOW,
            idempotency_key="key-1",
            payload_hash="h",
        )
    )
    with pytest.raises(ConflictError):
        repo.insert(
            ShortLink(
                code="k000002",
                target_url="https://example.com",
                created_at=NOW,
                idempotency_key="key-1",
                payload_hash="h",
            )
        )
    found = repo.get_by_idempotency_key("key-1")
    assert found is not None and found.code == "k000001"


@pytest.mark.req("FR-U10")
def test_concurrent_creates_yield_distinct_codes(db: Database) -> None:
    service = ShortenerService(
        links=SqlShortLinkRepository(db),
        analytics=SqlAnalyticsRepository(db),
        url_policy=UrlPolicy(),
    )
    with ThreadPoolExecutor(max_workers=8) as pool:
        links = list(
            pool.map(
                lambda i: service.create(CreateLinkCommand(target_url=f"https://example.com/{i}")),
                range(200),
            )
        )
    assert len({link.code for link in links}) == 200


@pytest.mark.req("FR-U07", "FR-U08", "FR-U10")
def test_analytics_summary_groups_by_day_and_survives_concurrency(db: Database) -> None:
    analytics = SqlAnalyticsRepository(db)
    events = [
        RedirectEvent(
            code="xyz9876", occurred_at=NOW + timedelta(hours=h), referrer=None, ua_class="other"
        )
        for h in (0, 1, 2, 25, 26, 49)
    ]
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(analytics.record, events))
    total, first, last, per_day = analytics.summary("xyz9876")
    assert total == 6
    assert first == NOW and last == NOW + timedelta(hours=49)
    assert per_day == {"2026-10-18": 3, "2026-10-19": 2, "2026-10-20": 1}


@pytest.mark.req("FR-U08")
def test_summary_for_unknown_code_is_empty(db: Database) -> None:
    assert SqlAnalyticsRepository(db).summary("nothing") == (0, None, None, {})


@pytest.mark.req("NFR-05")
def test_schema_version_recorded(db: Database) -> None:
    from sqlalchemy import select

    from agentic_sdlc.persistence.tables import SCHEMA_VERSION, schema_version

    with db.engine.connect() as conn:
        assert conn.execute(select(schema_version.c.version)).scalar_one() == SCHEMA_VERSION
