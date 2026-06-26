"""Dataset metadata PATCH integration tests."""

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_patch_dataset_metadata_in_draft(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    slug = f"patch-meta-{uuid.uuid4().hex[:8]}"
    created = await client.post(
        "/api/v1/datasets/",
        headers=auth_headers,
        json={"title": "Before patch", "slug": slug},
    )
    assert created.status_code == 201
    dataset_id = created.json()["data"]["id"]

    patched = await client.patch(
        f"/api/v1/datasets/{dataset_id}",
        headers=auth_headers,
        json={
            "title": "After patch",
            "description": "Updated description",
            "tags": ["finance", "test"],
            "metadata": {"dcat:title": "After patch"},
        },
    )
    assert patched.status_code == 200
    body = patched.json()["data"]
    assert body["title"] == "After patch"
    assert body["description"] == "Updated description"
    assert body["tags"] == ["finance", "test"]


@pytest.mark.asyncio
async def test_list_mine_returns_only_publisher_datasets(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    slug = f"mine-list-{uuid.uuid4().hex[:8]}"
    created = await client.post(
        "/api/v1/datasets/",
        headers=auth_headers,
        json={"title": "Mine filter test", "slug": slug},
    )
    assert created.status_code == 201
    dataset_id = created.json()["data"]["id"]

    mine = await client.get("/api/v1/datasets/?mine=true", headers=auth_headers)
    assert mine.status_code == 200
    ids = {item["id"] for item in mine.json()["data"]}
    assert dataset_id in ids
    for item in mine.json()["data"]:
        assert item["publisher_id"] == created.json()["data"]["publisher_id"]


@pytest.mark.asyncio
async def test_patch_published_dataset_rejected(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    from datetime import UTC, datetime

    from app.db.models import Dataset
    from app.db.session import tenant_write_session

    slug = f"patch-pub-{uuid.uuid4().hex[:8]}"
    created = await client.post(
        "/api/v1/datasets/",
        headers=auth_headers,
        json={"title": "Published", "slug": slug},
    )
    dataset_id = created.json()["data"]["id"]
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    async with tenant_write_session(tenant_id) as session:
        dataset = await session.get(Dataset, uuid.UUID(dataset_id))
        assert dataset is not None
        dataset.status = "published"
        dataset.published_at = datetime.now(UTC)
        await session.commit()

    patched = await client.patch(
        f"/api/v1/datasets/{dataset_id}",
        headers=auth_headers,
        json={"title": "Should fail"},
    )
    assert patched.status_code in {400, 422}
    assert patched.json()["errors"][0]["code"] == "VALIDATION_ERROR"
