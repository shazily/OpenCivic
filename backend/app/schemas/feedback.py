"""Pydantic schemas for feedback API."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class FeedbackCreateRequest(BaseModel):
    """Submit feedback on a published dataset."""

    dataset_id: uuid.UUID
    type: str = Field(..., pattern=r"^(rating|issue_report|correction_request|comment)$")
    rating: int | None = Field(default=None, ge=1, le=5)
    content: str | None = Field(default=None, max_length=5000)


class FeedbackResponse(BaseModel):
    """Feedback item returned by the API."""

    id: uuid.UUID
    dataset_id: uuid.UUID
    author_id: uuid.UUID | None
    type: str
    rating: int | None
    content: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
