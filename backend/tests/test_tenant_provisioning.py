"""Tenant provisioning tests."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

import app.db.session as db_session_module
from app.db.models import Licence, Tenant
from app.services.platform.tenant_provisioning_service import TenantProvisioningService


@pytest.mark.asyncio
async def test_create_tenant_requires_admin(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/admin/tenants",
        json={"slug": "demo-agency", "display_name": "Demo Agency"},
        headers={"Authorization": "Bearer dev-local-token-change-me"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_tenant_as_admin(client: AsyncClient) -> None:
    slug = f"agency-{uuid.uuid4().hex[:8]}"
    response = await client.post(
        "/api/v1/admin/tenants",
        json={"slug": slug, "display_name": "Test Agency"},
        headers={"Authorization": "Bearer dev-admin-token-change-me"},
    )
    assert response.status_code == 201
    body = response.json()["data"]
    assert body["slug"] == slug
    assert body["tier"] == "standard"
    assert body["status"] == "active"


@pytest.mark.asyncio
async def test_provisioning_service_seeds_licence() -> None:
    db_session_module._ensure_engines()
    assert db_session_module.AsyncWriteSession is not None
    slug = f"prov-{uuid.uuid4().hex[:8]}"
    tenant_id: uuid.UUID
    async with db_session_module.AsyncWriteSession() as session:
        tenant = await TenantProvisioningService().provision(
            session,
            slug=slug,
            display_name="Provision Test",
        )
        tenant_id = tenant.id
        await session.commit()

    async with db_session_module.AsyncWriteSession() as session:
        stored = await session.scalar(select(Tenant).where(Tenant.id == tenant_id))
        assert stored is not None
        assert stored.slug == slug
        await db_session_module.set_tenant_context(session, tenant_id)
        licence = await session.scalar(
            select(Licence).where(Licence.tenant_id == tenant_id)
        )
    assert licence is not None
    assert licence.name == "Open Government Licence"
