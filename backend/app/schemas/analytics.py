"""Pydantic schemas for analytics API."""

from pydantic import BaseModel


class DatasetUsageSummary(BaseModel):
    """Public usage counters for a dataset."""

    views: int
    downloads: int
    api_calls: int
    feedback_count: int
    average_rating: float | None


class DatasetEngagementPoint(BaseModel):
    """Single day in a dataset engagement trend."""

    date: str
    views: int
    downloads: int
    total: int


class PublisherUsageSummary(BaseModel):
    """Aggregated usage across a publisher's datasets."""

    dataset_count: int
    published_count: int
    views: int
    downloads: int
    api_calls: int
    ai_queries: int


class OrgUsageSummary(BaseModel):
    """Tenant-wide usage and inventory for org admins."""

    user_count: int
    dataset_count: int
    published_count: int
    views: int
    downloads: int
    api_calls: int
    ai_queries: int
