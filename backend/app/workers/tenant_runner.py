"""Iterate active tenants for background workers."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from sqlalchemy import select

from app.db.models import Tenant
from app.db.session import _ensure_engines, tenant_write_session


async def iter_active_tenant_ids() -> AsyncIterator[uuid.UUID]:
    """Yield tenant IDs for active platform tenants."""
    _ensure_engines()
    from app.db.session import AsyncReadSession

    async with AsyncReadSession() as session:
        result = await session.scalars(
            select(Tenant.id).where(Tenant.status == "active", Tenant.deleted_at.is_(None))
        )
        tenant_ids = list(result.all())

    for tenant_id in tenant_ids:
        yield tenant_id


async def run_for_all_tenants(handler) -> dict[str, object]:
    """Run an async handler per tenant inside a write session with RLS context."""
    results: dict[str, object] = {}
    async for tenant_id in iter_active_tenant_ids():
        async with tenant_write_session(tenant_id) as session:
            outcome = await handler(session, tenant_id)
            await session.commit()
        results[str(tenant_id)] = outcome
    return results
