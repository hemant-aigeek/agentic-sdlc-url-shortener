"""POST /api/v1/links, GET /api/v1/links/{code}, GET /api/v1/links/{code}/analytics."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request, Response, status

from agentic_sdlc.api.auth import get_settings, require_api_key
from agentic_sdlc.api.deps import get_limiter, get_shortener
from agentic_sdlc.api.ratelimit import TokenBucketLimiter
from agentic_sdlc.api.schemas import AnalyticsResponse, LinkCreateRequest, LinkResponse
from agentic_sdlc.config import Settings
from agentic_sdlc.domain.models import ShortLink
from agentic_sdlc.domain.service import CreateLinkCommand, ShortenerService

router = APIRouter(prefix="/api/v1/links", tags=["links"])


def _to_response(link: ShortLink, settings: Settings) -> LinkResponse:
    return LinkResponse(
        code=link.code,
        short_url=f"{settings.base_url.rstrip('/')}/{link.code}",
        target_url=link.target_url,
        created_at=link.created_at,
        expires_at=link.expires_at,
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=LinkResponse,
    responses={200: {"model": LinkResponse, "description": "Idempotent replay"}},
)
def create_link(
    body: LinkCreateRequest,
    request: Request,
    response: Response,
    api_key: str = Depends(require_api_key),
    settings: Settings = Depends(get_settings),  # noqa: B008
    service: ShortenerService = Depends(get_shortener),  # noqa: B008
    limiter: TokenBucketLimiter = Depends(get_limiter),  # noqa: B008
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
) -> LinkResponse:
    limiter.check(api_key)
    existing = service.get_by_idempotency_key(idempotency_key) if idempotency_key else None
    link = service.create(
        CreateLinkCommand(
            target_url=body.target_url,
            expires_at=body.expires_at,
            idempotency_key=idempotency_key,
        )
    )
    if existing is not None and existing.code == link.code:
        response.status_code = status.HTTP_200_OK
    response.headers["Location"] = f"/api/v1/links/{link.code}"
    return _to_response(link, settings)


@router.get("/{code}", response_model=LinkResponse)
def get_link(
    code: str,
    _: str = Depends(require_api_key),
    settings: Settings = Depends(get_settings),  # noqa: B008
    service: ShortenerService = Depends(get_shortener),  # noqa: B008
) -> LinkResponse:
    return _to_response(service.get(code), settings)


@router.get("/{code}/analytics", response_model=AnalyticsResponse)
def get_analytics(
    code: str,
    _: str = Depends(require_api_key),
    service: ShortenerService = Depends(get_shortener),  # noqa: B008
) -> AnalyticsResponse:
    summary = service.analytics(code)
    return AnalyticsResponse(
        code=summary.code,
        total_redirects=summary.total_redirects,
        first_redirect_at=summary.first_redirect_at,
        last_redirect_at=summary.last_redirect_at,
        redirects_by_day=summary.redirects_by_day,
    )
