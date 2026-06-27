"""Admin branding API tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_branding_as_admin(
    client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    response = await client.get("/api/v1/admin/branding", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()["data"]
    assert "tenant_id" in body
    assert "branding" in body


@pytest.mark.asyncio
async def test_patch_branding_as_admin(
    client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    patched = await client.patch(
        "/api/v1/admin/branding",
        headers=admin_headers,
        json={
            "primary_color": "#2563eb",
            "accent_color": "#f59e0b",
            "display_name": "Pilot Agency",
        },
    )
    assert patched.status_code == 200
    data = patched.json()["data"]
    assert data["display_name"] == "Pilot Agency"
    assert data["branding"]["primary_color"] == "#2563eb"

    fetched = await client.get("/api/v1/admin/branding", headers=admin_headers)
    assert fetched.status_code == 200
    assert fetched.json()["data"]["branding"]["primary_color"] == "#2563eb"


@pytest.mark.asyncio
async def test_patch_branding_rejects_publisher(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.patch(
        "/api/v1/admin/branding",
        headers=auth_headers,
        json={"primary_color": "#000000"},
    )
    assert response.status_code == 403
