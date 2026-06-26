"""MFA status endpoint."""

import os

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_mfa_status_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/mfa/status")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_mfa_status_for_publisher(client: AsyncClient) -> None:
    token = os.environ["OPENCIVIC_DEV_AUTH_TOKEN"]
    response = await client.get(
        "/api/v1/auth/mfa/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "mfa_enabled" in data
    assert "enrollment_required" in data
    assert "provider" in data
    assert data["keycloak_enabled"] is False
