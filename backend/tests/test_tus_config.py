"""TUS upload config endpoint tests."""

import os

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_tus_config_disabled_by_default(client: AsyncClient) -> None:
    headers = {"Authorization": f"Bearer {os.environ['DEV_AUTH_TOKEN']}"}
    response = await client.get("/api/v1/datasets/upload/tus-config", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["enabled"] is False
