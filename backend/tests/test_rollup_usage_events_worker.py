"""Celery rollup_usage_events maintenance task tests."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import set_tenant_context
from app.repositories.usage_event_repository import UsageEventRepository


@pytest.mark.asyncio
async def test_rollup_usage_events_worker(db_session: AsyncSession) -> None:
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    await set_tenant_context(db_session, tenant_id)
    repo = UsageEventRepository(db_session)
    await repo.record(tenant_id=tenant_id, event_type="api_call")
    await db_session.commit()

    await set_tenant_context(db_session, tenant_id)
    rolled = await repo.rollup_hourly()
    assert rolled >= 1
