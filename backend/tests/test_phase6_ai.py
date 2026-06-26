"""AI metadata and presigned download tests."""

import io
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.db.models import Dataset
from app.services.ai.metadata_service import suggest_dataset_metadata


@pytest.mark.asyncio
async def test_heuristic_metadata_suggestion() -> None:
    dataset = Dataset(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        title="Population by Region",
        slug="population-by-region",
        publisher_id=uuid.uuid4(),
        tags=["demographics"],
        schema_snapshot={
            "columns": [
                {"name": "region", "type": "string"},
                {"name": "population", "type": "integer"},
            ]
        },
        row_count=50,
    )
    result = await suggest_dataset_metadata(dataset)
    assert result["ai_assisted"] is False
    assert "description" in result
    assert result["metadata"]["dcat:theme"] == "demographics"


@pytest.mark.asyncio
async def test_suggest_metadata_endpoint(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    created = await client.post(
        "/api/v1/datasets/",
        headers=auth_headers,
        json={"title": "AI Meta Test", "slug": f"ai-meta-{uuid.uuid4().hex[:8]}"},
    )
    dataset_id = created.json()["data"]["id"]
    response = await client.post(
        f"/api/v1/datasets/{dataset_id}/suggest-metadata",
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert "description" in body
    assert "metadata" in body


@pytest.mark.asyncio
async def test_presigned_download_url(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session,
) -> None:
    from datetime import UTC, datetime

    from app.db.session import set_tenant_context
    from app.repositories.dataset_version_repository import DatasetVersionRepository

    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    slug = f"presign-{uuid.uuid4().hex[:8]}"
    created = await client.post(
        "/api/v1/datasets/",
        headers=auth_headers,
        json={"title": "Presign target", "slug": slug},
    )
    dataset_id = uuid.UUID(created.json()["data"]["id"])
    await set_tenant_context(db_session, tenant_id)
    dataset = await db_session.get(Dataset, dataset_id)
    assert dataset is not None
    dataset.status = "published"
    dataset.published_at = datetime.now(UTC)
    await DatasetVersionRepository(db_session).create(
        tenant_id=tenant_id,
        dataset_id=dataset_id,
        version_number=1,
        schema_snapshot={"columns": []},
        row_count=1,
        storage_path=f"parquet/{tenant_id}/{dataset_id}/v1.parquet",
        raw_file_path="raw/test.csv",
    )
    await db_session.commit()

    mock_storage = AsyncMock()
    mock_storage.presign_get = AsyncMock(return_value="https://minio.example/presigned")
    with patch(
        "app.api.v1.endpoints.datasets.get_storage_client",
        return_value=mock_storage,
    ):
        response = await client.get(f"/api/v1/datasets/{dataset_id}/download-url")
    assert response.status_code == 200
    assert response.json()["data"]["url"].startswith("https://")
