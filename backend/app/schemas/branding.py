"""Tenant white-label branding request/response schemas."""

import re
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator

_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
_HTTPS_URL = re.compile(r"^https://[^\s]+$")


class BrandingUpdate(BaseModel):
    """Partial branding update merged into tenant.config."""

    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    primary_color: str | None = None
    primary_hover_color: str | None = None
    accent_color: str | None = None
    logo_url: str | None = None

    @field_validator("primary_color", "primary_hover_color", "accent_color")
    @classmethod
    def validate_hex_color(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _HEX_COLOR.match(value):
            raise ValueError("Colour must be a hex value like #1a2b3c")
        return value

    @field_validator("logo_url")
    @classmethod
    def validate_logo_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _HTTPS_URL.match(value):
            raise ValueError("Logo URL must be an https:// URL")
        return value

    @model_validator(mode="after")
    def at_least_one_field(self) -> Self:
        if not any(
            getattr(self, field) is not None
            for field in ("display_name", "primary_color", "primary_hover_color", "accent_color", "logo_url")
        ):
            raise ValueError("At least one branding field is required")
        return self


class BrandingResponse(BaseModel):
    """Branding subset returned to admin and portal clients."""

    tenant_id: str
    slug: str
    display_name: str
    branding: dict[str, str]
