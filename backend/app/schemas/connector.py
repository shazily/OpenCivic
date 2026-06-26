"""Connector API schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ConnectorCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    type: str = Field(..., pattern=r"^(rest_api)$")
    config: dict[str, Any]
    dataset_id: uuid.UUID | None = None
    sync_frequency: str | None = "daily"


class ConnectorResponse(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    status: str
    circuit_state: str
    failure_count: int
    dataset_id: uuid.UUID | None
    last_sync_at: datetime | None
    next_sync_at: datetime | None
    sync_frequency: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
