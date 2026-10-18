"""Authentication assumptions (AMB-06).

A static API key protects mutating and non-public read endpoints; the
public redirect path is unauthenticated by design. Approval endpoints
additionally require an actor identity so decisions are attributable.
This is an explicit, documented assumption for the assessment — not a
substitute for an identity provider.
"""

from __future__ import annotations

import hmac

from fastapi import Depends, Header, Request

from agentic_sdlc.config import Settings
from agentic_sdlc.errors import UnauthorizedError

API_KEY_HEADER = "X-API-Key"
ACTOR_HEADER = "X-Actor"


def get_settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[no-any-return]


def require_api_key(
    settings: Settings = Depends(get_settings),  # noqa: B008
    x_api_key: str | None = Header(default=None, alias=API_KEY_HEADER),
) -> str:
    if not x_api_key or not hmac.compare_digest(x_api_key, settings.api_key):
        raise UnauthorizedError("a valid X-API-Key header is required")
    return x_api_key


def require_actor(
    _: str = Depends(require_api_key),
    x_actor: str | None = Header(default=None, alias=ACTOR_HEADER),
) -> str:
    actor = (x_actor or "").strip()
    if not actor:
        raise UnauthorizedError("an X-Actor header identifying the human decider is required")
    if len(actor) > 128:
        raise UnauthorizedError("X-Actor is too long")
    return actor
