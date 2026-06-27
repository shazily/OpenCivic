"""SCIM 2.0 user CRUD endpoint tests."""

import os
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import delete

from app.db.models import User
from app.db.session import tenant_write_session

SCIM_HEADERS = {"X-SCIM-Token": os.environ["SCIM_WEBHOOK_SECRET"]}


@pytest.mark.asyncio
async def test_scim_crud_lifecycle(client: AsyncClient) -> None:
    email = f"scim-{uuid.uuid4().hex[:8]}@test.local"
    tenant_id = uuid.UUID(os.environ["DEV_TENANT_ID"])

    create_response = await client.post(
        "/api/v1/scim/v2/Users",
        headers=SCIM_HEADERS,
        json={
            "userName": email,
            "name": {"formatted": "SCIM Test User"},
            "externalId": f"ext-{uuid.uuid4().hex[:8]}",
            "active": True,
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()
    user_id = created["id"]
    assert created["userName"] == email
    assert created["active"] is True

    get_response = await client.get(f"/api/v1/scim/v2/Users/{user_id}", headers=SCIM_HEADERS)
    assert get_response.status_code == 200
    assert get_response.json()["userName"] == email

    list_response = await client.get(
        "/api/v1/scim/v2/Users",
        headers=SCIM_HEADERS,
        params={"filter": f'userName eq "{email}"'},
    )
    assert list_response.status_code == 200
    resources = list_response.json()["Resources"]
    assert any(item["id"] == user_id for item in resources)

    patch_response = await client.patch(
        f"/api/v1/scim/v2/Users/{user_id}",
        headers=SCIM_HEADERS,
        json={"name": {"formatted": "SCIM Patched"}, "active": False},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["name"]["formatted"] == "SCIM Patched"
    assert patch_response.json()["active"] is False

    delete_response = await client.delete(f"/api/v1/scim/v2/Users/{user_id}", headers=SCIM_HEADERS)
    assert delete_response.status_code == 200
    assert delete_response.json()["active"] is False

    async with tenant_write_session(tenant_id) as session:
        await session.execute(delete(User).where(User.id == uuid.UUID(user_id)))


@pytest.mark.asyncio
async def test_scim_create_rejects_duplicate_email(client: AsyncClient) -> None:
    email = f"scim-dup-{uuid.uuid4().hex[:8]}@test.local"
    tenant_id = uuid.UUID(os.environ["DEV_TENANT_ID"])
    payload = {"userName": email, "name": {"formatted": "Dup User"}, "active": True}

    first = await client.post("/api/v1/scim/v2/Users", headers=SCIM_HEADERS, json=payload)
    assert first.status_code == 201
    user_id = first.json()["id"]

    second = await client.post("/api/v1/scim/v2/Users", headers=SCIM_HEADERS, json=payload)
    assert second.status_code == 409

    async with tenant_write_session(tenant_id) as session:
        await session.execute(delete(User).where(User.id == uuid.UUID(user_id)))


@pytest.mark.asyncio
async def test_scim_crud_rejects_bad_token(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/scim/v2/Users",
        headers={"X-SCIM-Token": "wrong"},
    )
    assert response.status_code == 401
