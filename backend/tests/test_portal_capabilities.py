"""Qdrant capability flag tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_portal_capabilities_reports_semantic_flag(client: AsyncClient) -> None:
    response = await client.get("/api/v1/portal/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert "semantic_search_available" in body["data"]
    assert "semantic_search_degraded" in body["data"]
    assert body["data"]["semantic_search_degraded"] is not body["data"]["semantic_search_available"]
