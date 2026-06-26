"""Celery rollup_usage_events maintenance task tests."""

import asyncio
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import set_tenant_context
from app.repositories.usage_event_repository import UsageEventRepository


@pytest.mark.asyncio
async def test_rollup_usage_events_worker(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    event_loop: asyncio.AbstractEventLoop,
) -> None:
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    await set_tenant_context(db_session, tenant_id)
    repo = UsageEventRepository(db_session)
    await repo.record(tenant_id=tenant_id, event_type="api_call")
    await db_session.commit()

    tenant_results: dict[str, object] = {}

    async def fake_run_for_all_tenants(handler) -> dict[str, object]:
        outcome = await handler(db_session, tenant_id)
        tenant_results[str(tenant_id)] = outcome
        return tenant_results

    def fake_run_async(coro: object) -> object:
        return event_loop.run_until_complete(coro)  # type: ignore[arg-type]

    monkeypatch.setattr(
        "app.workers.tenant_runner.run_for_all_tenants",
        fake_run_for_all_tenants,
    )
    monkeypatch.setattr("app.workers.async_runner.run_async", fake_run_async)

    from app.workers.tasks.tasks import rollup_usage_events

    result = rollup_usage_events()
    assert str(tenant_id) in result
    assert result[str(tenant_id)]["rolled_up"] >= 1
