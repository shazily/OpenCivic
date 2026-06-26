"""Pydantic schemas for dataset API requests and responses."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class DatasetCreate(BaseModel):
    """Payload for creating a new dataset draft."""

    title: str = Field(..., min_length=1, max_length=500)
    slug: str = Field(..., min_length=1, max_length=500, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str | None = None
    access_level: str = Field(default="public", pattern=r"^(public|restricted|private)$")
    licence_id: uuid.UUID | None = None
    tags: list[str] = Field(default_factory=list)


class DatasetUpdate(BaseModel):
    """Payload for updating dataset metadata (draft or changes_requested only)."""

    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    access_level: str | None = Field(default=None, pattern=r"^(public|restricted|private)$")
    licence_id: uuid.UUID | None = None
    tags: list[str] | None = None
    metadata: dict | None = None


class EmbargoScheduleRequest(BaseModel):
    """Schedule publication at a future datetime (embargo)."""

    embargo_until: datetime


class DownloadRecordRequest(BaseModel):
    """Record a client-side download for usage analytics."""

    format: str = Field(..., pattern=r"^(csv|json|parquet|arrow|xml)$")


class UploadSessionCreate(BaseModel):
    """Start a resumable chunked upload."""

    filename: str = Field(..., min_length=1, max_length=255)
    total_size: int = Field(..., gt=0)


class TusSessionCreate(BaseModel):
    """Start a TUS resumable upload session."""

    filename: str = Field(..., min_length=1, max_length=255)


class DatasetChatRequest(BaseModel):
    """Natural-language question about a published dataset."""

    question: str = Field(..., min_length=1, max_length=500)


class DatasetResponse(BaseModel):
    """Dataset representation returned by the API."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    title: str
    slug: str
    description: str | None
    status: str
    access_level: str
    licence_id: uuid.UUID | None
    publisher_id: uuid.UUID
    quality_score: Decimal | None
    staleness_state: str
    row_count: int | None = None
    file_size_bytes: int | None = None
    schema_snapshot: dict | None = None
    tags: list[str]
    metadata: dict = Field(default_factory=dict, validation_alias="metadata_")
    created_at: datetime
    published_at: datetime | None

    model_config = {"from_attributes": True}


class UploadResponseData(BaseModel):
    """Accepted upload job metadata."""

    job_id: str | None = None
    storage_key: str
    status: str = "queued"


class TusSessionResponseData(BaseModel):
    """TUS upload session metadata for the browser client."""

    endpoint: str
    storage_key: str
    upload_metadata: dict[str, str]


class UploadResponse(BaseModel):
    """202 Accepted response for dataset file upload."""

    data: UploadResponseData
    meta: dict = Field(default_factory=dict)
    errors: list[dict[str, str | None]] = Field(default_factory=list)


class PaginationMeta(BaseModel):
    """Cursor pagination metadata."""

    has_more: bool
    next_cursor: str | None
    total_count: int
    semantic_search_degraded: bool | None = None


class DatasetDataListResponse(BaseModel):
    """Paginated dataset row payload."""

    data: list[dict]
    meta: PaginationMeta
    errors: list[dict[str, str | None]] = Field(default_factory=list)


class DatasetListResponse(BaseModel):
    """Standard list envelope for datasets."""

    data: list[DatasetResponse]
    meta: PaginationMeta
    errors: list[dict[str, str | None]] = Field(default_factory=list)
