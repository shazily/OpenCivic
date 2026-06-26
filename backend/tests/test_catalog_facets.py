"""Catalog tag facet API tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_published_tag_facets(client: AsyncClient) -> None:
    response = await client.get("/api/v1/datasets/facets/tags")
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert isinstance(body["data"], list)
