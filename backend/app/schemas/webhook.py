"""Pydantic schemas for webhook endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class WebhookCreateRequest(BaseModel):
    """Payload for registering a webhook."""

    url: HttpUrl
    events: list[str] = Field(default_factory=lambda: ["DatasetPublished"])
    dataset_id: uuid.UUID | None = None


class WebhookResponse(BaseModel):
    """Webhook metadata (secret never returned)."""

    id: uuid.UUID
    url: str
    events: list[str]
    dataset_id: uuid.UUID | None
    status: str
    last_delivery_at: datetime | None
    failure_count: int
    created_by: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}
