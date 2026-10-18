"""Persistence ports for the application plane (NFR-07, ADR-003).

The domain depends on these abstract classes only; SQLite implementations live
in ``persistence/link_repository.py`` and tests use in-memory fakes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from agentic_sdlc.domain.models import RedirectEvent, ShortLink


class ShortLinkRepository(ABC):
    @abstractmethod
    def insert(self, link: ShortLink) -> ShortLink:
        """Persist a new link. Raises ``ConflictError`` on a duplicate code or key."""

    @abstractmethod
    def get_by_code(self, code: str) -> ShortLink | None: ...

    @abstractmethod
    def get_by_idempotency_key(self, key: str) -> ShortLink | None: ...


class AnalyticsRepository(ABC):
    @abstractmethod
    def record(self, event: RedirectEvent) -> None: ...

    @abstractmethod
    def summary(self, code: str) -> tuple[int, datetime | None, datetime | None, dict[str, int]]:
        """Return (total, first_at, last_at, per_day_counts)."""
