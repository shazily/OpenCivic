"""Webhook CRUD integration tests."""

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
async def test_create_list_delete_webhook(
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
            "/api/v1/webhooks/",
            headers=developer_headers,
            json={
                "url": "https://example.com/hooks/opencivic",
                "events": ["DatasetPublished"],
            },
        )
        assert created.status_code == 201
        webhook_id = created.json()["data"]["id"]

        listed = await client.get("/api/v1/webhooks/", headers=developer_headers)
        assert listed.status_code == 200
        assert any(item["id"] == webhook_id for item in listed.json()["data"])

        deleted = await client.delete(
            f"/api/v1/webhooks/{webhook_id}",
            headers=developer_headers,
        )
        assert deleted.status_code == 200
    finally:
        app.dependency_overrides.pop(get_current_user, None)
