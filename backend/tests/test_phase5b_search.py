"""Phase 5B/5D — parquet ingest, command palette, developer analytics."""

import io
import uuid

import pytest
from httpx import AsyncClient

from app.api.v1.dependencies.auth import CurrentUser, get_current_user
from app.db.models import Dataset
from app.db.session import set_tenant_context
from app.main import app
from app.services.ingest.schema_inference import infer_tabular_schema

DEVELOPER_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000012")


def _developer_headers() -> dict[str, str]:
    import os

    return {"Authorization": f"Bearer {os.environ['DEV_DEVELOPER_AUTH_TOKEN']}"}


@pytest.mark.asyncio
async def test_parquet_schema_inference() -> None:
    import pandas as pd

    buffer = io.BytesIO()
    pd.DataFrame({"name": ["a"], "value": [1]}).to_parquet(buffer, index=False)
    inferred = infer_tabular_schema(buffer.getvalue(), "sample.parquet")
    assert inferred.row_count == 1
    assert len(inferred.schema_snapshot["columns"]) == 2


@pytest.mark.asyncio
async def test_command_palette_search(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session,
) -> None:
    from datetime import UTC, datetime

    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    unique = uuid.uuid4().hex[:8]
    slug = f"palette-{unique}"
    title = f"Palette Unique {unique}"
    created = await client.post(
        "/api/v1/datasets/",
        headers=auth_headers,
        json={"title": title, "slug": slug},
    )
    dataset_id = created.json()["data"]["id"]
    await set_tenant_context(db_session, tenant_id)
    dataset = await db_session.get(Dataset, uuid.UUID(dataset_id))
    assert dataset is not None
    dataset.status = "published"
    dataset.published_at = datetime.now(UTC)
    await db_session.commit()

    response = await client.get(f"/api/v1/search/palette?q=Palette+Unique+{unique}")
    assert response.status_code == 200
    hits = response.json()["data"]
    assert any(item["id"] == dataset_id for item in hits)


@pytest.mark.asyncio
async def test_semantic_search_merge(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session,
) -> None:
    from datetime import UTC, datetime
    from unittest.mock import patch

    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    slug = f"semantic-{uuid.uuid4().hex[:8]}"
    created = await client.post(
        "/api/v1/datasets/",
        headers=auth_headers,
        json={"title": "Climate Emissions Data", "slug": slug},
    )
    dataset_id = created.json()["data"]["id"]
    await set_tenant_context(db_session, tenant_id)
    dataset = await db_session.get(Dataset, uuid.UUID(dataset_id))
    assert dataset is not None
    dataset.status = "published"
    dataset.description = "Greenhouse gas emissions by sector"
    dataset.published_at = datetime.now(UTC)
    await db_session.commit()

    with patch(
        "app.services.search.search_service.semantic_dataset_ids",
        return_value=[uuid.UUID(dataset_id)],
    ):
        response = await client.get("/api/v1/search/?q=emissions+sectors")
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["data"]]
    assert dataset_id in ids


@pytest.mark.asyncio
async def test_developer_rate_limits(
    client: AsyncClient,
) -> None:
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

    async def developer_auth() -> CurrentUser:
        return CurrentUser(
            user_id=DEVELOPER_USER_ID,
            tenant_id=tenant_id,
            roles=["developer"],
        )

    app.dependency_overrides[get_current_user] = developer_auth
    try:
        response = await client.get(
            "/api/v1/analytics/rate-limits",
            headers=_developer_headers(),
        )
        assert response.status_code == 200
        assert "data" in response.json()
    finally:
        app.dependency_overrides.pop(get_current_user, None)
