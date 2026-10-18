"""GET /{code} — the public, unversioned redirect path (FR-U05, FR-U06).

Unversioned on purpose: a short link printed on a poster must keep working
across API versions. 307 keeps the client's method; ``no-store`` makes sure
expiry and analytics are honoured on every visit.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from starlette.responses import RedirectResponse

from agentic_sdlc.api.deps import get_shortener
from agentic_sdlc.domain.codes import is_valid_code
from agentic_sdlc.domain.service import ShortenerService
from agentic_sdlc.errors import NotFoundError

router = APIRouter(tags=["redirect"])


@router.get("/{code}", status_code=307, response_class=RedirectResponse)
def follow(
    code: str,
    request: Request,
    service: ShortenerService = Depends(get_shortener),  # noqa: B008
) -> RedirectResponse:
    if not is_valid_code(code, request.app.state.settings.short_code_length):
        raise NotFoundError("short code not found")
    target = service.resolve(
        code,
        referrer=request.headers.get("referer"),
        user_agent=request.headers.get("user-agent"),
    )
    response = RedirectResponse(target, status_code=307)
    response.headers["Cache-Control"] = "no-store"
    return response
