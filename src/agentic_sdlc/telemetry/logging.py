"""structlog configuration.

Every log line carries whatever has been bound into the context (``run_id``,
``stage``, ``attempt``, ``correlation_id``) so a run can be reconstructed from
logs as well as from the event table (NFR-04). Secrets are redacted by key
(NFR-01).
"""

from __future__ import annotations

import logging
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

REDACTED_KEYS = frozenset({"api_key", "authorization", "x-api-key", "password", "secret", "token"})


def _redact(_: Any, __: str, event_dict: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    for key in list(event_dict):
        if key.lower() in REDACTED_KEYS:
            event_dict[key] = "***"
    return event_dict


def configure_logging(level: str = "INFO", json: bool = True) -> None:
    logging.basicConfig(level=level.upper(), stream=sys.stdout, format="%(message)s")
    renderer: Any = structlog.processors.JSONRenderer() if json else structlog.dev.ConsoleRenderer()
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _redact,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level.upper())),
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)  # type: ignore[no-any-return]


def bind(**kwargs: Any) -> None:
    structlog.contextvars.bind_contextvars(**kwargs)


def unbind(*keys: str) -> None:
    structlog.contextvars.unbind_contextvars(*keys)
