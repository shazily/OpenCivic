"""Publisher analytics API tests."""

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_publisher_usage_summary(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    slug = f"pub-analytics-{uuid.uuid4().hex[:8]}"
    await client.post(
        "/api/v1/datasets/",
        headers=auth_headers,
        json={"title": "Analytics Test", "slug": slug},
    )
    response = await client.get(
        "/api/v1/analytics/publisher/summary",
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["dataset_count"] >= 1
    assert "views" in body
    assert "downloads" in body
