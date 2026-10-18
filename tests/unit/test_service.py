"""FR-U01, U05–U09, U11: ShortenerService behaviour against in-memory fakes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from agentic_sdlc.domain.models import RedirectEvent, ShortLink
from agentic_sdlc.domain.ports import AnalyticsRepository, ShortLinkRepository
from agentic_sdlc.domain.service import CreateLinkCommand, ShortenerService
from agentic_sdlc.domain.validation import UrlPolicy
from agentic_sdlc.errors import (
    ConflictError,
    GoneError,
    NotFoundError,
    StoreUnavailableError,
    ValidationError,
)

pytestmark = pytest.mark.unit

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


class FakeLinks(ShortLinkRepository):
    def __init__(self) -> None:
        self.by_code: dict[str, ShortLink] = {}
        self.by_key: dict[str, ShortLink] = {}
        self.fail_next_insert = 0
        self.unavailable = False

    def insert(self, link: ShortLink) -> ShortLink:
        if self.unavailable:
            raise StoreUnavailableError("down")
        if self.fail_next_insert:
            self.fail_next_insert -= 1
            raise ConflictError("duplicate code")
        if link.code in self.by_code:
            raise ConflictError("duplicate code")
        self.by_code[link.code] = link
        if link.idempotency_key:
            self.by_key[link.idempotency_key] = link
        return link

    def get_by_code(self, code: str) -> ShortLink | None:
        if self.unavailable:
            raise StoreUnavailableError("down")
        return self.by_code.get(code)

    def get_by_idempotency_key(self, key: str) -> ShortLink | None:
        return self.by_key.get(key)


class FakeAnalytics(AnalyticsRepository):
    def __init__(self) -> None:
        self.events: list[RedirectEvent] = []
        self.fail = False

    def record(self, event: RedirectEvent) -> None:
        if self.fail:
            raise StoreUnavailableError("analytics down")
        self.events.append(event)

    def summary(self, code: str) -> tuple[int, datetime | None, datetime | None, dict[str, int]]:
        evs = [e for e in self.events if e.code == code]
        if not evs:
            return 0, None, None, {}
        per_day: dict[str, int] = {}
        for e in evs:
            per_day[e.occurred_at.date().isoformat()] = (
                per_day.get(e.occurred_at.date().isoformat(), 0) + 1
            )
        return len(evs), min(e.occurred_at for e in evs), max(e.occurred_at for e in evs), per_day


@pytest.fixture
def links() -> FakeLinks:
    return FakeLinks()


@pytest.fixture
def analytics() -> FakeAnalytics:
    return FakeAnalytics()


@pytest.fixture
def service(links: FakeLinks, analytics: FakeAnalytics) -> ShortenerService:
    return ShortenerService(
        links=links,
        analytics=analytics,
        url_policy=UrlPolicy(),
        code_length=7,
        max_code_attempts=3,
        clock=lambda: NOW,
    )


@pytest.mark.req("FR-U01")
def test_create_returns_link_with_code_and_timestamps(service: ShortenerService) -> None:
    link = service.create(CreateLinkCommand(target_url="https://example.com/a"))
    assert len(link.code) == 7
    assert link.target_url == "https://example.com/a"
    assert link.created_at == NOW
    assert link.expires_at is None


@pytest.mark.req("FR-U02")
def test_create_rejects_invalid_url(service: ShortenerService) -> None:
    with pytest.raises(ValidationError):
        service.create(CreateLinkCommand(target_url="javascript:alert(1)"))


@pytest.mark.req("FR-U06")
def test_create_rejects_expiry_in_the_past(service: ShortenerService) -> None:
    with pytest.raises(ValidationError) as exc:
        service.create(
            CreateLinkCommand(
                target_url="https://example.com", expires_at=NOW - timedelta(seconds=1)
            )
        )
    assert exc.value.field == "expires_at"


@pytest.mark.req("FR-U04")
def test_create_regenerates_code_on_collision(service: ShortenerService, links: FakeLinks) -> None:
    links.fail_next_insert = 2
    link = service.create(CreateLinkCommand(target_url="https://example.com"))
    assert link.code in links.by_code


@pytest.mark.req("FR-U04")
def test_create_gives_up_after_bounded_attempts(
    service: ShortenerService, links: FakeLinks
) -> None:
    links.fail_next_insert = 3
    with pytest.raises(StoreUnavailableError) as exc:
        service.create(CreateLinkCommand(target_url="https://example.com"))
    assert "attempts" in exc.value.detail
    assert links.by_code == {}


@pytest.mark.req("FR-U11")
def test_create_surfaces_store_unavailable(service: ShortenerService, links: FakeLinks) -> None:
    links.unavailable = True
    with pytest.raises(StoreUnavailableError):
        service.create(CreateLinkCommand(target_url="https://example.com"))


@pytest.mark.req("FR-U09")
def test_idempotent_create_same_key_same_payload_returns_existing(
    service: ShortenerService,
) -> None:
    cmd = CreateLinkCommand(target_url="https://example.com/x", idempotency_key="k1")
    first = service.create(cmd)
    second = service.create(cmd)
    assert first.code == second.code


@pytest.mark.req("FR-U09")
def test_idempotent_create_same_key_different_payload_conflicts(service: ShortenerService) -> None:
    service.create(CreateLinkCommand(target_url="https://example.com/x", idempotency_key="k1"))
    with pytest.raises(ConflictError):
        service.create(CreateLinkCommand(target_url="https://example.com/y", idempotency_key="k1"))


@pytest.mark.req("FR-U01")
def test_create_without_key_is_not_deduplicated(service: ShortenerService) -> None:
    a = service.create(CreateLinkCommand(target_url="https://example.com/x"))
    b = service.create(CreateLinkCommand(target_url="https://example.com/x"))
    assert a.code != b.code


@pytest.mark.req("FR-U05")
def test_resolve_returns_target_and_records_event(
    service: ShortenerService, analytics: FakeAnalytics
) -> None:
    link = service.create(CreateLinkCommand(target_url="https://example.com/a"))
    target = service.resolve(link.code, referrer="https://ref.example", user_agent="Mozilla/5.0")
    assert target == "https://example.com/a"
    assert len(analytics.events) == 1
    assert analytics.events[0].ua_class == "browser"


@pytest.mark.req("FR-U05")
def test_resolve_unknown_code_is_not_found(service: ShortenerService) -> None:
    with pytest.raises(NotFoundError):
        service.resolve("zzzzzzz")


@pytest.mark.req("FR-U06")
def test_resolve_expired_code_is_gone_not_not_found(
    service: ShortenerService, links: FakeLinks
) -> None:
    link = service.create(
        CreateLinkCommand(target_url="https://example.com", expires_at=NOW + timedelta(seconds=1))
    )
    service_later = ShortenerService(
        links=links,
        analytics=FakeAnalytics(),
        url_policy=UrlPolicy(),
        code_length=7,
        max_code_attempts=3,
        clock=lambda: NOW + timedelta(seconds=2),
    )
    with pytest.raises(GoneError):
        service_later.resolve(link.code)


@pytest.mark.req("FR-U07")
def test_analytics_failure_does_not_fail_redirect(
    service: ShortenerService, analytics: FakeAnalytics
) -> None:
    link = service.create(CreateLinkCommand(target_url="https://example.com/a"))
    analytics.fail = True
    assert service.resolve(link.code) == "https://example.com/a"


@pytest.mark.req("FR-U07")
@pytest.mark.parametrize(
    ("ua", "expected"),
    [
        ("Mozilla/5.0 (X11; Linux) Chrome/120", "browser"),
        ("Googlebot/2.1 (+http://www.google.com/bot.html)", "bot"),
        ("curl/8.0", "other"),
        (None, "other"),
    ],
)
def test_user_agent_classification(
    service: ShortenerService, analytics: FakeAnalytics, ua: str | None, expected: str
) -> None:
    link = service.create(CreateLinkCommand(target_url="https://example.com"))
    service.resolve(link.code, user_agent=ua)
    assert analytics.events[-1].ua_class == expected


@pytest.mark.req("FR-U08")
def test_analytics_summary(service: ShortenerService, analytics: FakeAnalytics) -> None:
    link = service.create(CreateLinkCommand(target_url="https://example.com"))
    analytics.events.extend(
        RedirectEvent(
            code=link.code, occurred_at=NOW + timedelta(days=d), referrer=None, ua_class="other"
        )
        for d in (0, 0, 1)
    )
    summary = service.analytics(link.code)
    assert summary.total_redirects == 3
    assert summary.first_redirect_at == NOW
    assert summary.last_redirect_at == NOW + timedelta(days=1)
    assert summary.redirects_by_day == {"2026-10-18": 2, "2026-10-19": 1}


@pytest.mark.req("FR-U08")
def test_analytics_unknown_code_is_not_found(service: ShortenerService) -> None:
    with pytest.raises(NotFoundError):
        service.analytics("nope123")


@pytest.mark.req("FR-U08")
def test_analytics_readable_for_expired_link(service: ShortenerService, links: FakeLinks) -> None:
    link = service.create(
        CreateLinkCommand(target_url="https://example.com", expires_at=NOW + timedelta(seconds=1))
    )
    later = ShortenerService(
        links=links,
        analytics=FakeAnalytics(),
        url_policy=UrlPolicy(),
        code_length=7,
        max_code_attempts=3,
        clock=lambda: NOW + timedelta(days=1),
    )
    assert later.analytics(link.code).total_redirects == 0
