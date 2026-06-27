"""SCIM webhook event and API key revocation tests."""

import os
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ApiKey, User
from app.db.session import set_tenant_context, tenant_write_session
from app.repositories.api_key_repository import ApiKeyRepository


@pytest.mark.asyncio
async def test_scim_webhook_user_deleted(client: AsyncClient, db_session: AsyncSession) -> None:
    del db_session
    tenant_id = uuid.UUID(os.environ["DEV_TENANT_ID"])
    steward_id = uuid.UUID(os.environ["DEV_STEWARD_USER_ID"])

    async with tenant_write_session(tenant_id) as session:
        user = await session.scalar(select(User).where(User.id == steward_id))
        assert user is not None
        email = user.email

    try:
        response = await client.post(
            "/api/v1/scim/webhook",
            json={"event": "user.deleted", "data": {"email": email}},
            headers={"X-SCIM-Token": os.environ["SCIM_WEBHOOK_SECRET"]},
        )
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "suspended"
    finally:
        async with tenant_write_session(tenant_id) as session:
            await session.execute(
                update(User).where(User.id == steward_id).values(status="active")
            )
            await session.commit()


@pytest.mark.asyncio
async def test_scim_suspend_revokes_api_keys(db_session: AsyncSession) -> None:
    from app.services.auth import scim_service

    tenant_id = uuid.UUID(os.environ["DEV_TENANT_ID"])
    developer_id = uuid.UUID(os.environ["DEV_DEVELOPER_USER_ID"])
    await set_tenant_context(db_session, tenant_id)

    key_repo = ApiKeyRepository(db_session)
    api_key, raw_key = await key_repo.create(
        owner_id=developer_id,
        tenant_id=tenant_id,
        name="SCIM revoke test",
        scopes=["read"],
    )
    assert raw_key

    user = await db_session.scalar(select(User).where(User.id == developer_id))
    assert user is not None
    assert user.status == "active"

    await scim_service.suspend_user(db_session, user, reason="test_suspend")
    await db_session.commit()

    await set_tenant_context(db_session, tenant_id)
    refreshed_key = await db_session.scalar(select(ApiKey).where(ApiKey.id == api_key.id))
    assert refreshed_key is not None
    assert refreshed_key.revoked_at is not None

    await db_session.execute(
        update(User).where(User.id == developer_id).values(status="active")
    )
    await db_session.commit()
