"""Admin jobs summary API stub."""

import os

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_admin_jobs_summary_requires_admin(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.get("/api/v1/admin/jobs/summary", headers=auth_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_jobs_summary_returns_queue_placeholders(client: AsyncClient) -> None:
    token = os.environ.get("OPENCIVIC_ADMIN_AUTH_TOKEN") or os.environ["OPENCIVIC_DEV_AUTH_TOKEN"]
    response = await client.get(
        "/api/v1/admin/jobs/summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["source"] in {"placeholder", "valkey", "valkey+flower", "flower", "flower+workers"}
    assert len(payload["queues"]) == 6
    assert payload["queues"][0]["name"] == "critical"
    assert "depth" in payload["queues"][0]
