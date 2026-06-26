"""Org admin analytics tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_org_usage_summary_requires_admin(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.get("/api/v1/analytics/org/summary", headers=auth_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_org_usage_summary_for_admin(client: AsyncClient) -> None:
    import os

    headers = {"Authorization": f"Bearer {os.environ['DEV_ADMIN_AUTH_TOKEN']}"}
    response = await client.get("/api/v1/analytics/org/summary", headers=headers)
    assert response.status_code == 200
    body = response.json()["data"]
    assert "user_count" in body
    assert "dataset_count" in body
    assert "api_calls" in body
