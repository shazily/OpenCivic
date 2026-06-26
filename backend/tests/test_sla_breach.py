"""Workflow SLA breach tests."""

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.db.models import Dataset, WorkflowSubmission
from app.db.session import set_tenant_context
from app.services.governance.workflow_service import WorkflowService


@pytest.mark.asyncio
async def test_flag_sla_breaches_marks_overdue(db_session) -> None:
    tenant_id = uuid.UUID(os.environ["DEV_TENANT_ID"])
    publisher_id = uuid.UUID(os.environ["DEV_USER_ID"])
    await set_tenant_context(db_session, tenant_id)

    dataset = Dataset(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        title="SLA Overdue Dataset",
        slug=f"sla-{uuid.uuid4().hex[:8]}",
        status="pending_review",
        publisher_id=publisher_id,
        row_count=10,
    )
    submission = WorkflowSubmission(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        dataset_id=dataset.id,
        maker_id=publisher_id,
        status="pending_review",
        submitted_at=datetime.now(UTC) - timedelta(days=3),
        review_due_at=datetime.now(UTC) - timedelta(hours=1),
        sla_breached=False,
    )
    db_session.add(dataset)
    db_session.add(submission)
    await db_session.commit()

    await set_tenant_context(db_session, tenant_id)
    service = WorkflowService(db_session, tenant_id)
    flagged = await service.flag_sla_breaches()
    await db_session.commit()

    assert submission.id in flagged
    updated = await db_session.get(WorkflowSubmission, submission.id)
    assert updated is not None
    assert updated.sla_breached is True
