"""Dataset data API integration tests."""

import io
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

SAMPLE_CSV = b"name,value\nalpha,1\nbeta,2\n"


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


@pytest.mark.asyncio
async def test_dataset_data_returns_rows_after_ingest(
    client: AsyncClient,
    auth_headers: dict[str, str],
    memory_storage,
    stub_celery_delay,
) -> None:
    from app.services.ingest.ingest_service import IngestService

    slug = f"data-api-{uuid.uuid4().hex[:8]}"
    created = await client.post(
        "/api/v1/datasets/",
        headers=auth_headers,
        json={"title": "Data API test", "slug": slug},
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

    data_response = await client.get(
        f"/api/v1/datasets/{dataset_id}/data",
        headers=auth_headers,
    )
    assert data_response.status_code == 200
    body = data_response.json()
    assert len(body["data"]) == 2
    assert body["meta"]["total_count"] == 2
    assert {row["name"] for row in body["data"]} == {"alpha", "beta"}


@pytest.mark.asyncio
async def test_dataset_data_without_ingest_returns_404(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    slug = f"no-data-{uuid.uuid4().hex[:8]}"
    created = await client.post(
        "/api/v1/datasets/",
        headers=auth_headers,
        json={"title": "Empty dataset", "slug": slug},
    )
    dataset_id = created.json()["data"]["id"]

    response = await client.get(
        f"/api/v1/datasets/{dataset_id}/data",
        headers=auth_headers,
    )
    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "DATASET_DATA_NOT_AVAILABLE"


@pytest.mark.asyncio
async def test_dataset_data_public_read_without_auth(
    client: AsyncClient,
    auth_headers: dict[str, str],
    memory_storage,
    stub_celery_delay,
    db_session,
) -> None:
    from app.api.v1.dependencies.auth import CurrentUser, get_current_user
    from app.db.models import User
    from app.db.session import set_tenant_context
    from app.main import app
    from app.services.ingest.ingest_service import IngestService
    from sqlalchemy import select

    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    steward_id = uuid.UUID("00000000-0000-0000-0000-000000000010")
    await set_tenant_context(db_session, tenant_id)
    existing = await db_session.scalar(select(User).where(User.id == steward_id))
    if existing is None:
        db_session.add(
            User(
                id=steward_id,
                tenant_id=tenant_id,
                keycloak_user_id="test-steward",
                email="steward@test.local",
                name="Test Steward",
                roles=["data_steward"],
            )
        )
        await db_session.commit()

    slug = f"public-data-{uuid.uuid4().hex[:8]}"
    created = await client.post(
        "/api/v1/datasets/",
        headers=auth_headers,
        json={"title": "Public read", "slug": slug},
    )
    dataset_id = created.json()["data"]["id"]

    upload = await client.post(
        f"/api/v1/datasets/{dataset_id}/upload",
        headers=auth_headers,
        files={"file": ("sample.csv", io.BytesIO(SAMPLE_CSV), "text/csv")},
    )
    assert upload.status_code == 202

    tenant_id_arg, queued_dataset_id, storage_key, filename, *_rest = stub_celery_delay["args"]
    await IngestService().run(
        tenant_id=uuid.UUID(str(tenant_id_arg)),
        dataset_id=uuid.UUID(str(queued_dataset_id)),
        storage_key=str(storage_key),
        filename=str(filename),
    )

    submit = await client.post(
        f"/api/v1/datasets/{dataset_id}/submit",
        headers=auth_headers,
        json={"notes": "Ready"},
    )
    assert submit.status_code == 202
    submission_id = submit.json()["data"]["id"]

    async def steward_auth() -> CurrentUser:
        return CurrentUser(user_id=steward_id, tenant_id=tenant_id, roles=["data_steward"])

    app.dependency_overrides[get_current_user] = steward_auth
    try:
        review = await client.post(
            f"/api/v1/workflow/{submission_id}/review",
            headers=auth_headers,
            json={"action": "approve", "notes": "Published"},
        )
        assert review.status_code == 200
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    response = await client.get(f"/api/v1/datasets/{dataset_id}/data")
    assert response.status_code == 200
    assert len(response.json()["data"]) == 2
