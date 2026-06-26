"""Review queue CSV export."""

import os

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_queue_export_requires_steward(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.get("/api/v1/workflow/queue/export", headers=auth_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_queue_export_csv_for_steward(client: AsyncClient) -> None:
    token = os.environ.get("OPENCIVIC_STEWARD_AUTH_TOKEN") or os.environ["OPENCIVIC_DEV_AUTH_TOKEN"]
    response = await client.get(
        "/api/v1/workflow/queue/export",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["format"] == "csv"
    assert payload["filename"] == "review-queue.csv"
    assert "id,dataset_id" in payload["content"]
