"""Dataset API integration tests."""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select


@pytest.mark.asyncio
async def test_create_list_get_dataset(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session,
) -> None:
    slug = f"test-dataset-{uuid.uuid4().hex[:8]}"
    create_response = await client.post(
        "/api/v1/datasets/",
        headers=auth_headers,
        json={
            "title": "Test Dataset",
            "slug": slug,
            "description": "Integration test dataset",
            "tags": ["test"],
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()["data"]
    assert created["title"] == "Test Dataset"
    assert created["slug"] == slug
    assert created["status"] == "draft"

    list_response = await client.get(
        "/api/v1/datasets/?filter[status]=draft&page_size=100",
        headers=auth_headers,
    )
    assert list_response.status_code == 200
    listed_ids = {item["id"] for item in list_response.json()["data"]}
    assert created["id"] in listed_ids

    get_response = await client.get(
        f"/api/v1/datasets/{created['id']}",
        headers=auth_headers,
    )
    assert get_response.status_code == 200
    assert get_response.json()["data"]["slug"] == slug

    from app.db.models import Event
    from app.db.session import set_tenant_context

    await set_tenant_context(db_session, uuid.UUID(created["tenant_id"]))
    event = await db_session.scalar(
        select(Event).where(
            Event.aggregate_id == uuid.UUID(created["id"]),
            Event.event_type == "DatasetCreated",
        )
    )
    assert event is not None


@pytest.mark.asyncio
async def test_create_requires_auth(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/datasets/",
        json={"title": "No Auth", "slug": "no-auth-dataset"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_rls_hides_other_tenant_dataset(
    client: AsyncClient,
    auth_headers: dict[str, str],
    other_tenant_dataset: uuid.UUID,
) -> None:
    list_response = await client.get("/api/v1/datasets/", headers=auth_headers)
    assert list_response.status_code == 200
    listed_ids = {item["id"] for item in list_response.json()["data"]}
    assert str(other_tenant_dataset) not in listed_ids

    get_response = await client.get(
        f"/api/v1/datasets/{other_tenant_dataset}",
        headers=auth_headers,
    )
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_slug_conflict(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    slug = f"duplicate-{uuid.uuid4().hex[:8]}"
    first = await client.post(
        "/api/v1/datasets/",
        headers=auth_headers,
        json={"title": "First", "slug": slug},
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/datasets/",
        headers=auth_headers,
        json={"title": "Second", "slug": slug},
    )
    assert second.status_code == 409
