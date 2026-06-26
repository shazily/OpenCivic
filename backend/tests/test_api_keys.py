"""API key CRUD integration tests."""

import uuid

import pytest
from httpx import AsyncClient

from app.api.v1.dependencies.auth import CurrentUser, get_current_user
from app.main import app

DEVELOPER_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000012")


@pytest.fixture
def developer_headers() -> dict[str, str]:
    import os

    return {"Authorization": f"Bearer {os.environ['DEV_DEVELOPER_AUTH_TOKEN']}"}


@pytest.mark.asyncio
async def test_create_list_revoke_api_key(
    client: AsyncClient,
    developer_headers: dict[str, str],
) -> None:
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

    async def developer_auth() -> CurrentUser:
        return CurrentUser(
            user_id=DEVELOPER_USER_ID,
            tenant_id=tenant_id,
            roles=["developer"],
        )

    app.dependency_overrides[get_current_user] = developer_auth
    try:
        created = await client.post(
            "/api/v1/api-keys/",
            headers=developer_headers,
            json={"name": "CI test key", "scopes": ["read"]},
        )
        assert created.status_code == 201
        body = created.json()["data"]
        assert body["name"] == "CI test key"
        assert body["raw_key"].startswith("oc_")
        key_id = body["id"]

        listed = await client.get("/api/v1/api-keys/", headers=developer_headers)
        assert listed.status_code == 200
        ids = {item["id"] for item in listed.json()["data"]}
        assert key_id in ids

        revoked = await client.delete(f"/api/v1/api-keys/{key_id}", headers=developer_headers)
        assert revoked.status_code == 200
        assert revoked.json()["data"]["revoked_at"] is not None
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_create_api_key_requires_developer_role(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.post(
        "/api/v1/api-keys/",
        headers=auth_headers,
        json={"name": "Should fail", "scopes": ["read"]},
    )
    assert response.status_code == 403
