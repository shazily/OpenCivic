"""Pydantic schemas for API key endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ApiKeyCreateRequest(BaseModel):
    """Payload for creating a new API key."""

    name: str = Field(..., min_length=1, max_length=255)
    scopes: list[str] = Field(default_factory=lambda: ["read"])
    expires_at: datetime | None = None


class ApiKeyResponse(BaseModel):
    """API key metadata (never includes raw key or hash)."""

    id: uuid.UUID
    name: str
    key_prefix: str
    scopes: list[str]
    owner_id: uuid.UUID
    rate_limit_override: int | None
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyCreatedResponse(BaseModel):
    """API key returned once at creation with the raw secret."""

    id: uuid.UUID
    name: str
    key_prefix: str
    scopes: list[str]
    raw_key: str = ""
    created_at: datetime

    model_config = {"from_attributes": True}
