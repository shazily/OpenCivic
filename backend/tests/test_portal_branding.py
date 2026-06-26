"""Portal branding endpoint tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_portal_branding_returns_tenant(client: AsyncClient) -> None:
    response = await client.get("/api/v1/portal/branding")
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["tenant_id"]
    assert body["display_name"]
    assert isinstance(body["branding"], dict)
