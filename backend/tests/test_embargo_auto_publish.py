"""Embargo auto-publish via Celery beat checker."""

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import encrypt
from app.db.models import Dataset, User
from app.db.session import set_tenant_context
from app.services.governance.workflow_service import WorkflowService


@pytest.mark.asyncio
async def test_embargo_auto_publish_when_due(db_session: AsyncSession) -> None:
    tenant_id = uuid.UUID(os.environ["DEV_TENANT_ID"])
    publisher_id = uuid.UUID(os.environ["DEV_USER_ID"])
    await set_tenant_context(db_session, tenant_id)

    publisher = await db_session.scalar(select(User).where(User.id == publisher_id))
    assert publisher is not None

    dataset_id = uuid.uuid4()
    past_embargo = datetime.now(UTC) - timedelta(minutes=10)
    db_session.add(
        Dataset(
            id=dataset_id,
            tenant_id=tenant_id,
            title="Embargo release test",
            slug=f"embargo-release-{dataset_id.hex[:8]}",
            publisher_id=publisher_id,
            status="scheduled",
            embargo_until=encrypt(past_embargo.isoformat()),
        )
    )
    await db_session.commit()

    await set_tenant_context(db_session, tenant_id)
    service = WorkflowService(db_session, tenant_id)
    released = await service.check_embargo_releases()
    await db_session.commit()

    assert dataset_id in released
    updated = await db_session.scalar(select(Dataset).where(Dataset.id == dataset_id))
    assert updated is not None
    assert updated.status == "published"
    assert updated.published_at is not None
    assert updated.embargo_until is None
