"""Database bootstrap.

One SQLAlchemy engine per process; sessions are short-lived and handed out by
``Database.session()``. Schema management for the assessment is ``create_all``
plus a ``schema_version`` row; Alembic is the documented upgrade path (ADR-003).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Connection, Engine, create_engine, event, insert, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from agentic_sdlc.errors import StoreUnavailableError
from agentic_sdlc.persistence.tables import SCHEMA_VERSION, metadata, schema_version


class Database:
    def __init__(self, url: str) -> None:
        self.url = url
        kwargs: dict[str, object] = {"future": True}
        if url.endswith(":memory:"):
            # One shared in-memory database for the whole process (tests).
            kwargs["connect_args"] = {"check_same_thread": False}
            kwargs["poolclass"] = StaticPool
        elif url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False, "timeout": 5}
        self.engine: Engine = create_engine(url, **kwargs)
        if url.startswith("sqlite"):
            event.listen(self.engine, "connect", _sqlite_pragmas)
        self._sessions = sessionmaker(bind=self.engine, expire_on_commit=False)

    def create_all(self) -> None:
        if self.url.startswith("sqlite") and not self.url.endswith(":memory:"):
            path = self.url.split("///", 1)[-1]
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        metadata.create_all(self.engine)
        with self.engine.begin() as conn:
            current = conn.execute(select(schema_version.c.version)).scalar_one_or_none()
            if current is None:
                conn.execute(insert(schema_version).values(version=SCHEMA_VERSION))

    def ping(self) -> bool:
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError:
            return False

    @contextmanager
    def connect(self) -> Iterator[Connection]:
        """Read-only connection; infrastructure errors become StoreUnavailableError."""
        try:
            with self.engine.connect() as conn:
                yield conn
        except IntegrityError:
            raise
        except SQLAlchemyError as exc:
            raise StoreUnavailableError("persistence unavailable") from exc

    @contextmanager
    def begin(self) -> Iterator[Connection]:
        """Transactional connection; IntegrityError passes through for callers to map."""
        try:
            with self.engine.begin() as conn:
                yield conn
        except IntegrityError:
            raise
        except SQLAlchemyError as exc:
            raise StoreUnavailableError("persistence unavailable") from exc

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self._sessions()
        try:
            yield session
            session.commit()
        except SQLAlchemyError as exc:
            session.rollback()
            raise StoreUnavailableError("persistence operation failed") from exc
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def dispose(self) -> None:
        self.engine.dispose()


def _sqlite_pragmas(dbapi_connection: object, _: object) -> None:
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()
