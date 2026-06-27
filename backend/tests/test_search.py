"""Postgres search integration tests."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Dataset
from app.db.session import set_tenant_context


@pytest.mark.asyncio
async def test_search_finds_matching_dataset(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    publisher_id = uuid.UUID("00000000-0000-0000-0000-000000000002")
    dataset_id = uuid.uuid4()
    unique_token = f"trgm-{uuid.uuid4().hex[:8]}"

    await set_tenant_context(db_session, tenant_id)
    db_session.add(
        Dataset(
            id=dataset_id,
            tenant_id=tenant_id,
            title=f"Inflation statistics {unique_token}",
            slug=f"inflation-{unique_token}",
            description="Consumer price index quarterly release",
            publisher_id=publisher_id,
            status="published",
            access_level="public",
            tags=["economy", "cpi"],
        )
    )
    await db_session.commit()

    response = await client.get(
        f"/api/v1/search/?q={unique_token}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["data"]}
    assert str(dataset_id) in ids


@pytest.mark.asyncio
async def test_search_requires_query(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.get("/api/v1/search/", headers=auth_headers)
    assert response.status_code == 422
