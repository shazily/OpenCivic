"""Feedback persistence — SQLAlchemy ORM only."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationError
from app.db.models import Dataset, Feedback

ALLOWED_TYPES = frozenset({"rating", "issue_report", "correction_request", "comment"})


class FeedbackRepository:
    """Tenant-scoped feedback operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        tenant_id: uuid.UUID,
        dataset_id: uuid.UUID,
        feedback_type: str,
        author_id: uuid.UUID | None,
        rating: int | None = None,
        content: str | None = None,
    ) -> Feedback:
        if feedback_type not in ALLOWED_TYPES:
            raise ValidationError(message=f"Invalid feedback type: {feedback_type}", field="type")
        if feedback_type == "rating" and rating is None:
            raise ValidationError(message="Rating is required for rating feedback.", field="rating")

        dataset = await self._session.scalar(
            select(Dataset).where(Dataset.id == dataset_id, Dataset.status == "published")
        )
        if dataset is None:
            raise ValidationError(
                message="Feedback is only accepted on published datasets.",
                field="dataset_id",
            )

        item = Feedback(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            dataset_id=dataset_id,
            author_id=author_id,
            type=feedback_type,
            rating=rating,
            content=content,
        )
        self._session.add(item)
        await self._session.flush()
        return item

    async def list_for_dataset(self, dataset_id: uuid.UUID) -> list[Feedback]:
        result = await self._session.scalars(
            select(Feedback)
            .where(Feedback.dataset_id == dataset_id)
            .order_by(Feedback.created_at.desc())
        )
        return list(result.all())

    async def summary_for_dataset(self, dataset_id: uuid.UUID) -> tuple[int, float | None]:
        count = await self._session.scalar(
            select(func.count()).select_from(Feedback).where(Feedback.dataset_id == dataset_id)
        )
        avg_rating = await self._session.scalar(
            select(func.avg(Feedback.rating))
            .where(Feedback.dataset_id == dataset_id)
            .where(Feedback.rating.is_not(None))
        )
        return int(count or 0), float(avg_rating) if avg_rating is not None else None
