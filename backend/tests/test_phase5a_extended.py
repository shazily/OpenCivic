"""Phase 5A extended — OpenAPI, downloads, rollups, webhook delivery."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.api.v1.dependencies.auth import CurrentUser, get_current_user
from app.db.models import Dataset
from app.db.session import set_tenant_context
from app.main import app
from app.repositories.usage_event_repository import UsageEventRepository
from app.services.analytics.usage_service import record_usage_event

DEVELOPER_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000012")


def _developer_headers() -> dict[str, str]:
    import os

    return {"Authorization": f"Bearer {os.environ['DEV_DEVELOPER_AUTH_TOKEN']}"}


@pytest.mark.asyncio
async def test_dataset_openapi_spec(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session,
) -> None:
    from datetime import UTC, datetime

    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    slug = f"openapi-{uuid.uuid4().hex[:8]}"
    created = await client.post(
        "/api/v1/datasets/",
        headers=auth_headers,
        json={"title": "OpenAPI target", "slug": slug},
    )
    dataset_id = created.json()["data"]["id"]
    await set_tenant_context(db_session, tenant_id)
    dataset = await db_session.get(Dataset, uuid.UUID(dataset_id))
    assert dataset is not None
    dataset.status = "published"
    dataset.published_at = datetime.now(UTC)
    dataset.schema_snapshot = {
        "columns": [
            {"name": "id", "type": "integer"},
            {"name": "name", "type": "string"},
        ]
    }
    await db_session.commit()

    response = await client.get(f"/api/v1/datasets/{dataset_id}/openapi.json")
    assert response.status_code == 200
    spec = response.json()["data"]
    assert spec["openapi"] == "3.1.0"
    assert f"/api/v1/datasets/{dataset_id}/data" in spec["paths"]


@pytest.mark.asyncio
async def test_record_download_event(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session,
) -> None:
    from datetime import UTC, datetime

    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    slug = f"download-{uuid.uuid4().hex[:8]}"
    created = await client.post(
        "/api/v1/datasets/",
        headers=auth_headers,
        json={"title": "Download target", "slug": slug},
    )
    dataset_id = created.json()["data"]["id"]
    await set_tenant_context(db_session, tenant_id)
    dataset = await db_session.get(Dataset, uuid.UUID(dataset_id))
    assert dataset is not None
    dataset.status = "published"
    dataset.published_at = datetime.now(UTC)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/datasets/{dataset_id}/download",
        json={"format": "csv"},
    )
    assert response.status_code == 202

    await record_usage_event(
        tenant_id=tenant_id,
        dataset_id=uuid.UUID(dataset_id),
        event_type="download",
        format_name="csv",
    )
    summary = await client.get(f"/api/v1/analytics/datasets/{dataset_id}/summary")
    assert summary.json()["data"]["downloads"] >= 1


@pytest.mark.asyncio
async def test_usage_hourly_rollup(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session,
) -> None:
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    slug = f"rollup-{uuid.uuid4().hex[:8]}"
    created = await client.post(
        "/api/v1/datasets/",
        headers=auth_headers,
        json={"title": "Rollup target", "slug": slug},
    )
    dataset_id = uuid.UUID(created.json()["data"]["id"])
    await set_tenant_context(db_session, tenant_id)
    repo = UsageEventRepository(db_session)
    await repo.record(
        tenant_id=tenant_id,
        event_type="view",
        dataset_id=dataset_id,
    )
    rolled = await repo.rollup_hourly(lookback_hours=1)
    assert rolled >= 1


@pytest.mark.asyncio
async def test_webhook_test_delivery(
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
    developer_headers = _developer_headers()
    try:
        created = await client.post(
            "/api/v1/webhooks/",
            headers=developer_headers,
            json={
                "url": "https://example.com/hooks/opencivic",
                "events": ["DatasetPublished"],
            },
        )
        webhook_id = created.json()["data"]["id"]

        with patch(
            "app.services.notifications.webhook_service.deliver_webhook_http",
            new_callable=AsyncMock,
            return_value=(200, "ok"),
        ):
            tested = await client.post(
                f"/api/v1/webhooks/{webhook_id}/test",
                headers=developer_headers,
            )
        assert tested.status_code == 202
        assert tested.json()["data"]["status"] == "ok"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
