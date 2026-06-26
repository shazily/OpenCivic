"""Authentication and RBAC tests."""
import uuid

import pytest
from httpx import AsyncClient

from app.api.v1.dependencies.auth import CurrentUser, get_current_user
from app.main import app


@pytest.mark.asyncio
async def test_auth_config_public(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/config")
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["dev_auth_enabled"] is True


@pytest.mark.asyncio
async def test_viewer_cannot_create_dataset(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000099")

    async def viewer_user() -> CurrentUser:
        return CurrentUser(user_id=user_id, tenant_id=tenant_id, roles=["viewer"])

    app.dependency_overrides[get_current_user] = viewer_user
    try:
        response = await client.post(
            "/api/v1/datasets/",
            headers=auth_headers,
            json={"title": "Forbidden", "slug": "viewer-forbidden"},
        )
        assert response.status_code == 403
        assert response.json()["errors"][0]["code"] == "PERMISSION_DENIED"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
