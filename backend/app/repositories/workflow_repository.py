"""Workflow submission persistence — SQLAlchemy ORM only."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.db.models import Dataset, WorkflowSubmission


class WorkflowRepository:
    """Tenant-scoped workflow submission queries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, submission_id: uuid.UUID) -> WorkflowSubmission:
        submission = await self._session.scalar(
            select(WorkflowSubmission).where(WorkflowSubmission.id == submission_id)
        )
        if submission is None:
            raise NotFound(message="Workflow submission not found.")
        return submission

    async def list_pending_review(self) -> list[WorkflowSubmission]:
        result = await self._session.scalars(
            select(WorkflowSubmission)
            .where(WorkflowSubmission.status == "pending_review")
            .order_by(WorkflowSubmission.submitted_at.asc())
        )
        return list(result.all())

    async def list_pending_approval(self) -> list[WorkflowSubmission]:
        result = await self._session.scalars(
            select(WorkflowSubmission)
            .where(WorkflowSubmission.status == "pending_approval")
            .order_by(WorkflowSubmission.submitted_at.asc())
        )
        return list(result.all())

    async def get_active_for_dataset(self, dataset_id: uuid.UUID) -> WorkflowSubmission | None:
        return await self._session.scalar(
            select(WorkflowSubmission)
            .where(
                WorkflowSubmission.dataset_id == dataset_id,
                WorkflowSubmission.status.in_(
                    ("pending_review", "changes_requested", "pending_approval")
                ),
            )
            .order_by(WorkflowSubmission.submitted_at.desc())
            .limit(1)
        )

    async def list_overdue_pending(self) -> list[WorkflowSubmission]:
        """Submissions past review_due_at that are not yet flagged."""
        now = datetime.now(UTC)
        result = await self._session.scalars(
            select(WorkflowSubmission)
            .where(
                WorkflowSubmission.status.in_(("pending_review", "pending_approval")),
                WorkflowSubmission.sla_breached.is_(False),
                WorkflowSubmission.review_due_at.isnot(None),
                WorkflowSubmission.review_due_at < now,
            )
            .order_by(WorkflowSubmission.review_due_at.asc())
        )
        return list(result.all())

    async def governance_summary(self, *, days: int = 30) -> dict[str, int]:
        """Counts for steward governance dashboard."""
        since = datetime.now(UTC) - timedelta(days=days)
        status_counts = await self._session.execute(
            select(WorkflowSubmission.status, func.count()).group_by(WorkflowSubmission.status)
        )
        by_status = {row[0]: int(row[1]) for row in status_counts.all()}
        sla_breached = await self._session.scalar(
            select(func.count())
            .select_from(WorkflowSubmission)
            .where(WorkflowSubmission.sla_breached.is_(True))
        )
        published_recent = await self._session.scalar(
            select(func.count())
            .select_from(Dataset)
            .where(Dataset.status == "published", Dataset.published_at >= since)
        )
        return {
            "pending_review": by_status.get("pending_review", 0),
            "pending_approval": by_status.get("pending_approval", 0),
            "changes_requested": by_status.get("changes_requested", 0),
            "sla_breached": int(sla_breached or 0),
            "published_last_30_days": int(published_recent or 0),
            "report_days": days,
        }
