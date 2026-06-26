"""
OpenCivic — Governance workflow service.
Implements the maker-checker state machine.
RULE: Self-approval enforced at DB constraint level (checker_id != maker_id).
Application-level check here is secondary defence only.
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
    DatasetNotFound,
    InvalidWorkflowTransition,
    SelfApprovalNotAllowed,
)
from app.db.models import Dataset, WorkflowSubmission

logger = structlog.get_logger(__name__)

# Valid state transitions
TRANSITIONS: dict[str, list[str]] = {
    "draft":             ["pending_review"],
    "pending_review":    ["changes_requested", "pending_approval", "published", "rejected"],
    "changes_requested": ["pending_review"],
    "pending_approval":  ["published", "rejected"],
    "scheduled":         ["published"],
    "published":         ["archived"],
    "rejected":          [],
    "archived":          [],
}


class WorkflowService:

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def submit(self, dataset_id: uuid.UUID, maker_id: uuid.UUID, notes: str = "") -> WorkflowSubmission:
        """Submit dataset for review. draft → pending_review."""
        dataset = await self._get_dataset(dataset_id)
        self._assert_transition(dataset.status, "pending_review")

        review_due = datetime.now(UTC) + timedelta(hours=settings.WORKFLOW_REVIEW_SLA_HOURS)
        submission = WorkflowSubmission(
            dataset_id=dataset_id,
            maker_id=maker_id,
            status="pending_review",
            maker_notes=notes,
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
        RULE: checker_id != maker_id — checked here AND enforced at DB constraint.
        """
        result = await self.session.execute(
            select(WorkflowSubmission).where(WorkflowSubmission.id == submission_id)
        )
        submission = result.scalar_one_or_none()
        if not submission:
            raise DatasetNotFound(message="Submission not found.")

        # Application-level self-approval check (DB constraint is primary)
        if submission.maker_id == checker_id:
            raise SelfApprovalNotAllowed(
                message="You cannot review your own submission. A different user must review it."
            )

        action_map = {
            "approve": "pending_approval",
            "reject": "rejected",
            "request_changes": "changes_requested",
        }
        if action not in action_map:
            raise InvalidWorkflowTransition(message=f"Invalid action: {action}")

        new_status = action_map[action]
        self._assert_transition(submission.status, new_status)

        submission.checker_id = checker_id
        submission.status = new_status
        submission.checker_notes = notes
        submission.reviewed_at = datetime.now(UTC)
        if submission.review_due_at and datetime.now(UTC) > submission.review_due_at:
            submission.sla_breached = True

        await self.session.execute(
            update(Dataset).where(Dataset.id == submission.dataset_id).values(status=new_status)
        )
        await self._emit_event(f"Dataset{action.title()}", submission.dataset_id, checker_id, {"notes": notes})
        return submission

    async def approve(self, submission_id: uuid.UUID, approver_id: uuid.UUID, notes: str = "") -> WorkflowSubmission:
        """Senior approver signs off (high-sensitivity two-gate workflow)."""
        result = await self.session.execute(
            select(WorkflowSubmission).where(WorkflowSubmission.id == submission_id)
        )
        submission = result.scalar_one_or_none()
        if not submission:
            raise DatasetNotFound(message="Submission not found.")

        if submission.maker_id == approver_id or submission.checker_id == approver_id:
            raise SelfApprovalNotAllowed(message="Approver must be different from maker and checker.")

        self._assert_transition(submission.status, "published")
        submission.approver_id = approver_id
        submission.status = "published"
        submission.approver_notes = notes
        submission.approved_at = datetime.now(UTC)

        await self.session.execute(
            update(Dataset).where(Dataset.id == submission.dataset_id).values(
                status="published", published_at=datetime.now(UTC)
            )
        )
        await self._emit_event("DatasetPublished", submission.dataset_id, approver_id, {})
        return submission

    async def schedule(self, dataset_id: uuid.UUID, embargo_until: datetime, actor_id: uuid.UUID) -> None:
        """Set embargo. embargo_until is ENCRYPTED before storage."""
        encrypted = encrypt(embargo_until.isoformat())
        await self.session.execute(
            update(Dataset).where(Dataset.id == dataset_id).values(
                status="scheduled", embargo_until=encrypted
            )
        )
        await self._emit_event("DatasetScheduled", dataset_id, actor_id, {})

    async def check_embargo_releases(self) -> list[uuid.UUID]:
        """Check for scheduled datasets whose embargo has passed. Called by Celery Beat."""
        result = await self.session.execute(
            select(Dataset).where(Dataset.status == "scheduled")
        )
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
                        update(Dataset).where(Dataset.id == dataset.id).values(
                            status="published", published_at=now, embargo_until=None
                        )
                    )
                    released.append(dataset.id)
                    logger.info("embargo_released", dataset_id=str(dataset.id))
            except Exception as e:
                logger.error("embargo_check_failed", dataset_id=str(dataset.id), error=str(e))
        return released

    def _assert_transition(self, current: str, target: str) -> None:
        allowed = TRANSITIONS.get(current, [])
        if target not in allowed:
            raise InvalidWorkflowTransition(
                message=f"Cannot transition from '{current}' to '{target}'. "
                        f"Allowed transitions: {allowed}"
            )

    async def _get_dataset(self, dataset_id: uuid.UUID) -> Dataset:
        result = await self.session.execute(select(Dataset).where(Dataset.id == dataset_id))
        dataset = result.scalar_one_or_none()
        if not dataset:
            raise DatasetNotFound(message=f"Dataset {dataset_id} not found.")
        return dataset

    async def _emit_event(self, event_type: str, aggregate_id: uuid.UUID, actor_id: uuid.UUID, payload: dict) -> None:
        """Write to the CQRS event store. INSERT ONLY — never update or delete."""
        from app.db.models import Event
        event = Event(
            event_type=event_type,
            aggregate_id=aggregate_id,
            aggregate_type="Dataset",
            actor_id=actor_id,
            actor_type="user",
            payload=payload,
        )
        self.session.add(event)
