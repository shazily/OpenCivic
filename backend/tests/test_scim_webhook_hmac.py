"""SCIM webhook HMAC signature verification."""

import hashlib
import hmac
import os
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.db.session import tenant_write_session
from app.db.models import User


def _sign(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


@pytest.mark.asyncio
async def test_scim_webhook_accepts_hmac_signature(client: AsyncClient) -> None:
    tenant_id = uuid.UUID(os.environ["DEV_TENANT_ID"])
    steward_id = uuid.UUID(os.environ["DEV_STEWARD_USER_ID"])
    secret = os.environ["SCIM_WEBHOOK_SECRET"]

    async with tenant_write_session(tenant_id) as session:
        user = await session.scalar(select(User).where(User.id == steward_id))
        assert user is not None
        email = user.email

    payload = b'{"event":"user.deleted","data":{"email":"' + email.encode() + b'"}}'
    try:
        response = await client.post(
            "/api/v1/scim/webhook",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-SCIM-Signature": _sign(payload, secret),
            },
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
async def test_scim_webhook_rejects_invalid_hmac(client: AsyncClient) -> None:
    payload = b'{"event":"user.deleted","data":{"email":"nobody@test.local"}}'
    response = await client.post(
        "/api/v1/scim/webhook",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "X-SCIM-Signature": "sha256=deadbeef",
        },
    )
    assert response.status_code == 401
