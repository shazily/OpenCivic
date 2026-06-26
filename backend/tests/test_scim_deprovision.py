"""SCIM deprovision webhook tests."""

import os
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.session import tenant_write_session


@pytest.mark.asyncio
async def test_scim_deprovision_by_email(client: AsyncClient, db_session: AsyncSession) -> None:
    del db_session
    tenant_id = uuid.UUID(os.environ["DEV_TENANT_ID"])
    publisher_id = uuid.UUID(os.environ["DEV_USER_ID"])

    async with tenant_write_session(tenant_id) as session:
        user = await session.scalar(select(User).where(User.id == publisher_id))
        assert user is not None
        publisher_email = user.email

    try:
        response = await client.post(
            "/api/v1/scim/deprovision",
            json={"email": publisher_email},
            headers={"X-SCIM-Token": os.environ["SCIM_WEBHOOK_SECRET"]},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["status"] == "suspended"
        assert body["data"]["user_id"] == str(publisher_id)

        async with tenant_write_session(tenant_id) as session:
            updated = await session.scalar(select(User).where(User.id == publisher_id))
            assert updated is not None
            assert updated.status == "suspended"
    finally:
        async with tenant_write_session(tenant_id) as session:
            await session.execute(
                update(User)
                .where(User.id == publisher_id)
                .values(status="active")
            )


@pytest.mark.asyncio
async def test_scim_deprovision_rejects_bad_token(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/scim/deprovision",
        json={"email": "steward@test.local"},
        headers={"X-SCIM-Token": "wrong-token"},
    )
    assert response.status_code == 401
