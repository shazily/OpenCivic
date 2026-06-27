"""Feedback and usage analytics integration tests."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.api.v1.dependencies.auth import CurrentUser, get_current_user
from app.db.models import Dataset
from app.db.session import set_tenant_context
from app.main import app


@pytest.mark.asyncio
async def test_submit_feedback_on_published_dataset(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session,
) -> None:
    from datetime import UTC, datetime

    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    slug = f"feedback-{uuid.uuid4().hex[:8]}"
    created = await client.post(
        "/api/v1/datasets/",
        headers=auth_headers,
        json={"title": "Feedback target", "slug": slug},
    )
    dataset_id = created.json()["data"]["id"]
    await set_tenant_context(db_session, tenant_id)
    dataset = await db_session.get(Dataset, uuid.UUID(dataset_id))
    assert dataset is not None
    dataset.status = "published"
    dataset.published_at = datetime.now(UTC)
    await db_session.commit()

    response = await client.post(
        "/api/v1/feedback/",
        json={
            "dataset_id": dataset_id,
            "type": "rating",
            "rating": 5,
            "content": "Great data",
        },
    )
    assert response.status_code == 201
    assert response.json()["data"]["rating"] == 5


@pytest.mark.asyncio
async def test_dataset_usage_summary(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session,
) -> None:
    from datetime import UTC, datetime

    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    slug = f"stats-{uuid.uuid4().hex[:8]}"
    created = await client.post(
        "/api/v1/datasets/",
        headers=auth_headers,
        json={"title": "Stats target", "slug": slug},
    )
    dataset_id = created.json()["data"]["id"]
    await set_tenant_context(db_session, tenant_id)
    dataset = await db_session.get(Dataset, uuid.UUID(dataset_id))
    assert dataset is not None
    dataset.status = "published"
    dataset.published_at = datetime.now(UTC)
    await db_session.commit()

    await client.get(f"/api/v1/datasets/{dataset_id}", headers=auth_headers)

    from app.services.analytics.usage_service import record_usage_event

    await record_usage_event(
        tenant_id=tenant_id,
        dataset_id=uuid.UUID(dataset_id),
        event_type="view",
    )

    summary = await client.get(f"/api/v1/analytics/datasets/{dataset_id}/summary")
    assert summary.status_code == 200
    body = summary.json()["data"]
    assert body["views"] >= 1


@pytest.mark.asyncio
async def test_users_me(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.get("/api/v1/users/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["data"]["roles"]
