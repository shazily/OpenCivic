"""Connector circuit breaker integration tests."""

import os
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import set_tenant_context
from app.repositories.connector_repository import ConnectorRepository


@pytest.mark.asyncio
async def test_connector_circuit_opens_after_failure_threshold(db_session: AsyncSession) -> None:
    tenant_id = uuid.UUID(os.environ["DEV_TENANT_ID"])
    user_id = uuid.UUID(os.environ["DEV_USER_ID"])
    await set_tenant_context(db_session, tenant_id)

    repo = ConnectorRepository(db_session)
    connector = await repo.create(
        tenant_id=tenant_id,
        name=f"Circuit test {uuid.uuid4().hex[:6]}",
        type_name="rest_api",
        config={"url": "https://example.invalid"},
        created_by=user_id,
    )
    threshold = settings.CONNECTOR_CIRCUIT_BREAKER_THRESHOLD

    for _ in range(threshold - 1):
        await repo.mark_sync_failure(connector.id, threshold)
    mid = await repo.get_by_id(connector.id)
    assert mid.circuit_state != "open"

    await repo.mark_sync_failure(connector.id, threshold)
    opened = await repo.get_by_id(connector.id)
    assert opened.circuit_state == "open"
    assert opened.failure_count >= threshold


@pytest.mark.asyncio
async def test_open_circuit_excluded_from_due_syncs(db_session: AsyncSession) -> None:
    tenant_id = uuid.UUID(os.environ["DEV_TENANT_ID"])
    user_id = uuid.UUID(os.environ["DEV_USER_ID"])
    await set_tenant_context(db_session, tenant_id)

    repo = ConnectorRepository(db_session)
    connector = await repo.create(
        tenant_id=tenant_id,
        name=f"Open circuit {uuid.uuid4().hex[:6]}",
        type_name="rest_api",
        config={"url": "https://example.invalid"},
        created_by=user_id,
    )
    threshold = settings.CONNECTOR_CIRCUIT_BREAKER_THRESHOLD
    for _ in range(threshold):
        await repo.mark_sync_failure(connector.id, threshold)

    due = await repo.get_due_syncs()
    assert all(item.id != connector.id for item in due)

    await repo.close_circuit(connector.id)
    closed = await repo.get_by_id(connector.id)
    assert closed.circuit_state == "closed"
    assert closed.failure_count == 0
