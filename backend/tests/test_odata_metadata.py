"""OData $metadata XML stub."""

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.db.models import Dataset
from app.db.session import set_tenant_context


@pytest.mark.asyncio
async def test_odata_metadata_requires_published_dataset(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    slug = f"odata-meta-{uuid.uuid4().hex[:8]}"
    created = await client.post(
        "/api/v1/datasets/",
        headers=auth_headers,
        json={"title": "OData meta draft", "slug": slug},
    )
    dataset_id = created.json()["data"]["id"]
    response = await client.get(f"/api/v1/datasets/{dataset_id}/odata/$metadata")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_odata_metadata_xml_for_published(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session,
) -> None:
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    slug = f"odata-pub-{uuid.uuid4().hex[:8]}"
    created = await client.post(
        "/api/v1/datasets/",
        headers=auth_headers,
        json={"title": "OData published", "slug": slug},
    )
    dataset_id = created.json()["data"]["id"]
    await set_tenant_context(db_session, tenant_id)
    dataset = await db_session.get(Dataset, uuid.UUID(dataset_id))
    assert dataset is not None
    dataset.status = "published"
    dataset.published_at = datetime.now(UTC)
    dataset.schema_snapshot = {
        "columns": [
            {"name": "region", "type": "string"},
            {"name": "value", "type": "integer"},
        ]
    }
    await db_session.commit()

    response = await client.get(f"/api/v1/datasets/{dataset_id}/odata/$metadata")
    assert response.status_code == 200
    assert "application/xml" in response.headers.get("content-type", "")
    body = response.text
    assert "edmx:Edmx" in body
    assert slug.replace("-", "_") in body
    assert 'Property Name="region"' in body
