"""Versioned request/response schemas for the application plane (plan §2).

``SCHEMA_VERSION`` is exported into ``contracts/schemas`` and bumps only
through change control (policy CHG-002). Additive changes are compatible;
removing or retyping a field is breaking.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0.0"


class _Versioned(BaseModel):
    model_config = ConfigDict(json_schema_extra={"x-schema-version": SCHEMA_VERSION})


class LinkCreateRequest(_Versioned):
    target_url: str = Field(..., examples=["https://example.com/docs"], max_length=4096)
    expires_at: datetime | None = Field(default=None, description="UTC; must be in the future")


class LinkResponse(_Versioned):
    code: str
    short_url: str
    target_url: str
    created_at: datetime
    expires_at: datetime | None


class AnalyticsResponse(_Versioned):
    code: str
    total_redirects: int
    first_redirect_at: datetime | None
    last_redirect_at: datetime | None
    redirects_by_day: dict[str, int]
    consistency: str = Field(
        default="eventual",
        description="Redirect events are recorded best-effort after the redirect (AMB-05).",
    )


class Problem(_Versioned):
    type: str
    title: str
    status: int
    detail: str
    instance: str
    errors: list[dict[str, str]] | None = None
