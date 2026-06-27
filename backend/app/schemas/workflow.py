"""Pydantic schemas for governance workflow API."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class GovernanceSummary(BaseModel):
    """Aggregate governance queue metrics for stewards."""

    pending_review: int
    pending_approval: int
    changes_requested: int
    sla_breached: int
    published_last_30_days: int
    report_days: int = 30


class SubmitForReviewRequest(BaseModel):
    """Publisher submission notes."""

    notes: str = Field(default="", max_length=5000)


class ReviewActionRequest(BaseModel):
    """Steward review decision."""

    action: str = Field(..., pattern=r"^(approve|reject|request_changes)$")
    notes: str = Field(default="", max_length=5000)


class ApproveActionRequest(BaseModel):
    """Senior approver decision for high-sensitivity datasets."""

    notes: str = Field(default="", max_length=5000)


class WorkflowSubmissionResponse(BaseModel):
    """Workflow submission representation."""

    id: uuid.UUID
    dataset_id: uuid.UUID
    maker_id: uuid.UUID
    checker_id: uuid.UUID | None
    approver_id: uuid.UUID | None
    status: str
    maker_notes: str | None
    checker_notes: str | None
    submitted_at: datetime
    review_due_at: datetime | None
    reviewed_at: datetime | None
    approved_at: datetime | None
    sla_breached: bool

    model_config = {"from_attributes": True}
