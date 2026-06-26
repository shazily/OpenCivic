"""
OpenCivic — Governance workflow service.
Implements the maker-checker state machine (standard one-gate variant).
RULE: Self-approval enforced at DB constraint level (checker_id != maker_id).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.encryption import decrypt, encrypt
from app.core.errors import (
    DatasetDataNotAvailable,
    DatasetNotFound,
    InvalidWorkflowTransition,
    SelfApprovalNotAllowed,
    ValidationError,
)
from app.db.models import Dataset, User, WorkflowSubmission
from app.repositories.workflow_repository import WorkflowRepository
from app.services.events.event_publisher import EventPublisher

logger = structlog.get_logger(__name__)

TRANSITIONS: dict[str, list[str]] = {
    "draft": ["pending_review"],
    "pending_review": ["changes_requested", "pending_approval", "published", "rejected"],
    "changes_requested": ["pending_review"],
    "pending_approval": ["published", "rejected"],
    "scheduled": ["published"],
    "published": ["archived"],
    "rejected": [],
    "archived": [],
}


class WorkflowService:
    """Maker-checker workflow orchestration for a tenant."""

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def flag_sla_breaches(self) -> list[uuid.UUID]:
        """Mark overdue pending submissions as SLA breached and notify stewards."""
        from app.services.notifications.in_app_service import InAppNotificationService

        repo = WorkflowRepository(self.session)
        overdue = await repo.list_overdue_pending()
        flagged: list[uuid.UUID] = []
        for submission in overdue:
            submission.sla_breached = True
            flagged.append(submission.id)
            await self._emit_event(
                "WorkflowSlaBreached",
                submission.dataset_id,
                submission.maker_id,
                {
                    "submission_id": str(submission.id),
                    "review_due_at": submission.review_due_at.isoformat()
                    if submission.review_due_at
                    else None,
                },
            )
            stewards = await self.session.scalars(
                select(User).where(User.roles.contains(["data_steward"]))
            )
            dataset = await self._get_dataset(submission.dataset_id)
            for steward in stewards.all():
                await InAppNotificationService.push(
                    tenant_id=self.tenant_id,
                    user_id=steward.id,
                    title="Review SLA breached",
                    body=f'"{dataset.title}" is overdue for steward review.',
                    event_type="WorkflowSlaBreached",
                    link="/portal/review",
                )
                from app.workers.tasks.tasks import send_email

                send_email.delay(
                    steward.email,
                    "OpenCivic: review SLA breached",
                    (
                        f"<p>Dataset <strong>{dataset.title}</strong> is overdue for steward review.</p>"
                        f'<p><a href="/portal/review">Open review queue</a></p>'
                    ),
                    idempotency_key=f"sla-breach:{submission.id}:{steward.id}",
                )
        if flagged:
            logger.info("workflow_sla_flagged", count=len(flagged))
        return flagged

    async def submit(
        self,
        dataset_id: uuid.UUID,
        maker_id: uuid.UUID,
        notes: str = "",
    ) -> WorkflowSubmission:
        """Submit dataset for review. draft/changes_requested → pending_review."""
        dataset = await self._get_dataset(dataset_id)
        if dataset.publisher_id != maker_id:
            raise ValidationError(
                message="Only the dataset publisher can submit for review.",
                field="dataset_id",
            )
        if dataset.row_count is None:
            raise DatasetDataNotAvailable(
                message="Upload and ingest data before submitting for review.",
            )
        self._assert_transition(dataset.status, "pending_review")

        review_due = datetime.now(UTC) + timedelta(hours=settings.WORKFLOW_REVIEW_SLA_HOURS)
        submission = WorkflowSubmission(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            dataset_id=dataset_id,
            maker_id=maker_id,
            status="pending_review",
            maker_notes=notes or None,
            submitted_at=datetime.now(UTC),
            review_due_at=review_due,
        )
        self.session.add(submission)
        await self.session.execute(
            update(Dataset).where(Dataset.id == dataset_id).values(status="pending_review")
        )
        await self._emit_event("DatasetSubmitted", dataset_id, maker_id, {"notes": notes})
        logger.info("dataset_submitted", dataset_id=str(dataset_id), maker_id=str(maker_id))
        return submission

    async def review(
        self,
        submission_id: uuid.UUID,
        checker_id: uuid.UUID,
        action: str,
        notes: str = "",
    ) -> WorkflowSubmission:
        """
        Steward reviews submission. action: approve | reject | request_changes.
        Standard workflow: approve → published (one-gate).
        """
        submission = await self._get_submission(submission_id)

        if submission.maker_id == checker_id:
            raise SelfApprovalNotAllowed(
                message="You cannot review your own submission. A different user must review it."
            )

        action_map = {
            "approve": "published",
            "reject": "rejected",
            "request_changes": "changes_requested",
        }
        if action not in action_map:
            raise InvalidWorkflowTransition(message=f"Invalid action: {action}")

        dataset = await self._get_dataset(submission.dataset_id)
        if action == "approve" and dataset.workflow_variant == "high_sensitivity":
            new_status = "pending_approval"
        else:
            new_status = action_map[action]
        self._assert_transition(submission.status, new_status)

        now = datetime.now(UTC)
        submission.checker_id = checker_id
        submission.status = new_status
        submission.checker_notes = notes or None
        submission.reviewed_at = now
        if submission.review_due_at and now > submission.review_due_at:
            submission.sla_breached = True

        dataset_values: dict[str, object] = {"status": new_status}
        if new_status == "published":
            submission.approved_at = now
            dataset_values["published_at"] = now
            dataset = await self._get_dataset(submission.dataset_id)
            from app.services.analytics.quality_scoring_service import compute_quality_score

            dataset_values["quality_score"] = compute_quality_score(dataset)

        await self.session.execute(
            update(Dataset).where(Dataset.id == submission.dataset_id).values(**dataset_values)
        )

        publish_event = (
            "DatasetPublished" if new_status == "published" else "DatasetPendingApproval"
        )
        event_type = {
            "approve": publish_event,
            "reject": "DatasetRejected",
            "request_changes": "DatasetChangesRequested",
        }[action]
        await self._emit_event(
            event_type,
            submission.dataset_id,
            checker_id,
            {"notes": notes, "submission_id": str(submission_id)},
        )
        return submission

    async def approve(
        self,
        submission_id: uuid.UUID,
        approver_id: uuid.UUID,
        notes: str = "",
    ) -> WorkflowSubmission:
        """Senior approver signs off (high-sensitivity two-gate workflow)."""
        submission = await self._get_submission(submission_id)

        if submission.maker_id == approver_id or submission.checker_id == approver_id:
            raise SelfApprovalNotAllowed(
                message="Approver must be different from maker and checker."
            )

        self._assert_transition(submission.status, "published")
        now = datetime.now(UTC)
        submission.approver_id = approver_id
        submission.status = "published"
        submission.approver_notes = notes or None
        submission.approved_at = now

        await self.session.execute(
            update(Dataset)
            .where(Dataset.id == submission.dataset_id)
            .values(status="published", published_at=now)
        )
        dataset = await self._get_dataset(submission.dataset_id)
        from app.services.analytics.quality_scoring_service import compute_quality_score

        await self.session.execute(
            update(Dataset)
            .where(Dataset.id == submission.dataset_id)
            .values(quality_score=compute_quality_score(dataset))
        )
        await self._emit_event("DatasetPublished", submission.dataset_id, approver_id, {})
        return submission

    async def archive(self, dataset_id: uuid.UUID, actor_id: uuid.UUID) -> Dataset:
        """Retire a published dataset."""
        dataset = await self._get_dataset(dataset_id)
        self._assert_transition(dataset.status, "archived")
        await self.session.execute(
            update(Dataset).where(Dataset.id == dataset_id).values(status="archived")
        )
        dataset.status = "archived"
        await self._emit_event("DatasetArchived", dataset_id, actor_id, {})
        return dataset

    async def schedule(
        self, dataset_id: uuid.UUID, embargo_until: datetime, actor_id: uuid.UUID
    ) -> None:
        """Set embargo. embargo_until is ENCRYPTED before storage."""
        encrypted = encrypt(embargo_until.isoformat())
        await self.session.execute(
            update(Dataset)
            .where(Dataset.id == dataset_id)
            .values(status="scheduled", embargo_until=encrypted)
        )
        await self._emit_event("DatasetScheduled", dataset_id, actor_id, {})

    async def check_embargo_releases(self) -> list[uuid.UUID]:
        """Check for scheduled datasets whose embargo has passed. Called by Celery Beat."""
        result = await self.session.execute(select(Dataset).where(Dataset.status == "scheduled"))
        datasets = result.scalars().all()
        released = []
        now = datetime.now(UTC)
        for dataset in datasets:
            if not dataset.embargo_until:
                continue
            try:
                embargo_dt = datetime.fromisoformat(decrypt(dataset.embargo_until))
                if now >= embargo_dt.replace(tzinfo=UTC):
                    await self.session.execute(
                        update(Dataset)
                        .where(Dataset.id == dataset.id)
                        .values(status="published", published_at=now, embargo_until=None)
                    )
                    released.append(dataset.id)
                    logger.info("embargo_released", dataset_id=str(dataset.id))
            except Exception as exc:
                logger.error("embargo_check_failed", dataset_id=str(dataset.id), error=str(exc))
        return released

    def _assert_transition(self, current: str, target: str) -> None:
        allowed = TRANSITIONS.get(current, [])
        if target not in allowed:
            raise InvalidWorkflowTransition(
                message=f"Cannot transition from '{current}' to '{target}'. "
                f"Allowed transitions: {allowed}"
            )

    async def _get_dataset(self, dataset_id: uuid.UUID) -> Dataset:
        dataset = await self.session.scalar(select(Dataset).where(Dataset.id == dataset_id))
        if dataset is None:
            raise DatasetNotFound(message="Dataset not found.")
        return dataset

    async def _get_submission(self, submission_id: uuid.UUID) -> WorkflowSubmission:
        submission = await self.session.scalar(
            select(WorkflowSubmission).where(WorkflowSubmission.id == submission_id)
        )
        if submission is None:
            raise DatasetNotFound(message="Workflow submission not found.")
        return submission

    async def _emit_event(
        self,
        event_type: str,
        aggregate_id: uuid.UUID,
        actor_id: uuid.UUID,
        payload: dict,
    ) -> None:
        await EventPublisher.publish(
            self.session,
            tenant_id=self.tenant_id,
            event_type=event_type,
            aggregate_id=aggregate_id,
            aggregate_type="dataset",
            actor_id=actor_id,
            payload=payload,
        )
        from app.services.notifications.webhook_service import enqueue_matching_webhooks

        await enqueue_matching_webhooks(
            self.session,
            tenant_id=self.tenant_id,
            event_type=event_type,
            dataset_id=aggregate_id,
            payload=payload,
        )
        if event_type == "DatasetPublished":
            from app.workers.tasks.tasks import index_dataset_search

            index_dataset_search.delay(str(self.tenant_id), str(aggregate_id))
