"""Tests for embargo scheduling API."""

import io
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.api.v1.dependencies.auth import CurrentUser, get_current_user
from app.main import app

SAMPLE_CSV = b"name,value\nalpha,1\nbeta,2\n"
STEWARD_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000010")


@pytest.fixture
async def steward_user(db_session) -> uuid.UUID:
    from app.db.models import User
    from app.db.session import set_tenant_context

    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    await set_tenant_context(db_session, tenant_id)
    existing = await db_session.scalar(select(User).where(User.id == STEWARD_USER_ID))
    if existing is None:
        db_session.add(
            User(
                id=STEWARD_USER_ID,
                tenant_id=tenant_id,
                keycloak_user_id="test-steward",
                email="steward@test.local",
                name="Test Steward",
                roles=["data_steward"],
            )
        )
        await db_session.commit()
    return STEWARD_USER_ID


@pytest.fixture
def steward_headers() -> dict[str, str]:
    import os

    return {"Authorization": f"Bearer {os.environ['DEV_STEWARD_AUTH_TOKEN']}"}


@pytest.fixture
def memory_storage(monkeypatch: pytest.MonkeyPatch):
    from tests.fakes.memory_storage import MemoryStorageClient

    client = MemoryStorageClient()
    for target in (
        "app.services.storage.storage_client.get_storage_client",
        "app.api.v1.endpoints.datasets.get_storage_client",
        "app.services.ingest.ingest_service.get_storage_client",
        "app.services.data.dataset_data_reader.get_storage_client",
    ):
        monkeypatch.setattr(target, lambda: client)
    return client


@pytest.fixture
def stub_celery_delay(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, tuple] = {}

    class FakeAsyncResult:
        id = "test-job-id"

    def fake_delay(*args: object, **kwargs: object) -> FakeAsyncResult:
        captured["args"] = args
        return FakeAsyncResult()

    monkeypatch.setattr(
        "app.api.v1.endpoints.datasets.process_upload.delay",
        fake_delay,
    )
    return captured


async def _ingested_dataset(
    client: AsyncClient,
    auth_headers: dict[str, str],
    memory_storage,
    stub_celery_delay,
) -> str:
    from app.services.ingest.ingest_service import IngestService

    slug = f"embargo-{uuid.uuid4().hex[:8]}"
    created = await client.post(
        "/api/v1/datasets/",
        headers=auth_headers,
        json={"title": "Embargo test", "slug": slug},
    )
    assert created.status_code == 201
    dataset_id = created.json()["data"]["id"]

    upload = await client.post(
        f"/api/v1/datasets/{dataset_id}/upload",
        headers=auth_headers,
        files={"file": ("sample.csv", io.BytesIO(SAMPLE_CSV), "text/csv")},
    )
    assert upload.status_code == 202

    tenant_id, queued_dataset_id, storage_key, filename, *_rest = stub_celery_delay["args"]
    publisher_id = _rest[1] if len(_rest) > 1 else None
    await IngestService().run(
        tenant_id=uuid.UUID(str(tenant_id)),
        dataset_id=uuid.UUID(str(queued_dataset_id)),
        storage_key=str(storage_key),
        filename=str(filename),
        publisher_id=uuid.UUID(str(publisher_id)) if publisher_id else None,
    )
    return dataset_id


@pytest.mark.asyncio
async def test_schedule_embargo_requires_auth(client: AsyncClient) -> None:
    response = await client.post(
        f"/api/v1/datasets/{uuid.uuid4()}/schedule",
        json={"embargo_until": (datetime.now(UTC) + timedelta(days=1)).isoformat()},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_schedule_embargo_on_pending_review(
    client: AsyncClient,
    auth_headers: dict[str, str],
    steward_headers: dict[str, str],
    steward_user: uuid.UUID,
    memory_storage,
    stub_celery_delay,
) -> None:
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    dataset_id = await _ingested_dataset(client, auth_headers, memory_storage, stub_celery_delay)

    submit = await client.post(
        f"/api/v1/datasets/{dataset_id}/submit",
        headers=auth_headers,
        json={"notes": "ready"},
    )
    assert submit.status_code == 202

    async def steward_auth() -> CurrentUser:
        return CurrentUser(user_id=steward_user, tenant_id=tenant_id, roles=["data_steward"])

    app.dependency_overrides[get_current_user] = steward_auth
    try:
        embargo_until = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
        response = await client.post(
            f"/api/v1/datasets/{dataset_id}/schedule",
            json={"embargo_until": embargo_until},
            headers=steward_headers,
        )
        assert response.status_code == 202
        assert response.json()["data"]["status"] == "scheduled"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_schedule_embargo_rejects_past_datetime(
    client: AsyncClient,
    auth_headers: dict[str, str],
    steward_headers: dict[str, str],
    steward_user: uuid.UUID,
    memory_storage,
    stub_celery_delay,
) -> None:
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    dataset_id = await _ingested_dataset(client, auth_headers, memory_storage, stub_celery_delay)
    await client.post(
        f"/api/v1/datasets/{dataset_id}/submit",
        headers=auth_headers,
        json={"notes": "ready"},
    )

    async def steward_auth() -> CurrentUser:
        return CurrentUser(user_id=steward_user, tenant_id=tenant_id, roles=["data_steward"])

    app.dependency_overrides[get_current_user] = steward_auth
    try:
        past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        response = await client.post(
            f"/api/v1/datasets/{dataset_id}/schedule",
            json={"embargo_until": past},
            headers=steward_headers,
        )
        assert response.status_code == 400
    finally:
        app.dependency_overrides.pop(get_current_user, None)
