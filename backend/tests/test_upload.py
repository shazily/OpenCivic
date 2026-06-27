"""Dataset upload and ingest integration tests."""

import io
import os
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

SAMPLE_CSV = b"name,value\nalpha,1\nbeta,2\n"


@pytest.fixture
def memory_storage(monkeypatch: pytest.MonkeyPatch):
    """Replace Minio with in-memory storage for upload tests."""
    from tests.fakes.memory_storage import MemoryStorageClient

    client = MemoryStorageClient()
    for target in (
        "app.services.storage.storage_client.get_storage_client",
        "app.api.v1.endpoints.datasets.get_storage_client",
        "app.services.ingest.ingest_service.get_storage_client",
    ):
        monkeypatch.setattr(target, lambda: client)
    return client


@pytest.fixture
def stub_celery_delay(monkeypatch: pytest.MonkeyPatch):
    """Capture enqueue calls without running ingest inside the API event loop."""
    captured: dict[str, tuple] = {}

    class FakeAsyncResult:
        id = "test-job-id"

    def fake_delay(*args: object, **kwargs: object) -> FakeAsyncResult:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return FakeAsyncResult()

    monkeypatch.setattr(
        "app.api.v1.endpoints.datasets.process_upload.delay",
        fake_delay,
    )
    return captured


async def _create_dataset(client: AsyncClient, auth_headers: dict[str, str]) -> str:
    slug = f"upload-test-{uuid.uuid4().hex[:8]}"
    response = await client.post(
        "/api/v1/datasets/",
        headers=auth_headers,
        json={"title": "Upload test", "slug": slug},
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


@pytest.mark.asyncio
async def test_upload_csv_queues_ingest(
    client: AsyncClient,
    auth_headers: dict[str, str],
    memory_storage,
    stub_celery_delay,
) -> None:
    dataset_id = await _create_dataset(client, auth_headers)
    response = await client.post(
        f"/api/v1/datasets/{dataset_id}/upload",
        headers=auth_headers,
        files={"file": ("sample.csv", io.BytesIO(SAMPLE_CSV), "text/csv")},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["data"]["status"] == "queued"
    assert body["data"]["job_id"] == "test-job-id"
    storage_key = body["data"]["storage_key"]
    assert storage_key in memory_storage.objects
    assert stub_celery_delay["args"][1] == dataset_id


@pytest.mark.asyncio
async def test_upload_rejects_non_csv(
    client: AsyncClient,
    auth_headers: dict[str, str],
    memory_storage,
    stub_celery_delay,
) -> None:
    dataset_id = await _create_dataset(client, auth_headers)
    response = await client.post(
        f"/api/v1/datasets/{dataset_id}/upload",
        headers=auth_headers,
        files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "INVALID_FILE_FORMAT"


@pytest.mark.asyncio
async def test_upload_wrong_publisher(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session,
    memory_storage,
    stub_celery_delay,
) -> None:
    from app.db.models import Dataset, User
    from app.db.session import set_tenant_context

    tenant_id = uuid.UUID(os.environ["DEV_TENANT_ID"])
    other_publisher_id = uuid.uuid4()
    dataset_id = uuid.uuid4()

    await set_tenant_context(db_session, tenant_id)
    db_session.add(
        User(
            id=other_publisher_id,
            tenant_id=tenant_id,
            keycloak_user_id=f"other-publisher-{other_publisher_id.hex[:8]}",
            email="other-publisher@test.local",
            name="Other Publisher",
            roles=["data_publisher"],
        )
    )
    await db_session.flush()
    db_session.add(
        Dataset(
            id=dataset_id,
            tenant_id=tenant_id,
            title="Other publisher dataset",
            slug=f"other-pub-{dataset_id.hex[:8]}",
            publisher_id=other_publisher_id,
            status="draft",
        )
    )
    await db_session.commit()

    response = await client.post(
        f"/api/v1/datasets/{dataset_id}/upload",
        headers=auth_headers,
        files={"file": ("sample.csv", io.BytesIO(SAMPLE_CSV), "text/csv")},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_ingest_eager_updates_dataset(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session,
    memory_storage,
    stub_celery_delay,
) -> None:
    from app.services.ingest.ingest_service import IngestService

    dataset_id = await _create_dataset(client, auth_headers)
    upload_response = await client.post(
        f"/api/v1/datasets/{dataset_id}/upload",
        headers=auth_headers,
        files={"file": ("sample.csv", io.BytesIO(SAMPLE_CSV), "text/csv")},
    )
    assert upload_response.status_code == 202

    tenant_id, queued_dataset_id, storage_key, filename, *_rest = stub_celery_delay["args"]
    publisher_id = _rest[1] if len(_rest) > 1 else None
    await IngestService().run(
        tenant_id=uuid.UUID(str(tenant_id)),
        dataset_id=uuid.UUID(str(queued_dataset_id)),
        storage_key=str(storage_key),
        filename=str(filename),
        publisher_id=uuid.UUID(str(publisher_id)) if publisher_id else None,
    )

    get_response = await client.get(
        f"/api/v1/datasets/{dataset_id}",
        headers=auth_headers,
    )
    assert get_response.status_code == 200
    data = get_response.json()["data"]
    assert data["row_count"] == 2
    assert data["schema_snapshot"] is not None
    assert len(data["schema_snapshot"]["columns"]) == 2

    from app.db.models import DatasetVersion, Event
    from app.db.session import set_tenant_context

    tenant_id = uuid.UUID(data["tenant_id"])
    await set_tenant_context(db_session, tenant_id)
    version = await db_session.scalar(
        select(DatasetVersion).where(DatasetVersion.dataset_id == uuid.UUID(dataset_id))
    )
    assert version is not None
    assert version.version_number == 1
    assert version.row_count == 2

    event = await db_session.scalar(
        select(Event).where(
            Event.aggregate_id == uuid.UUID(dataset_id),
            Event.event_type == "DatasetIngested",
        )
    )
    assert event is not None


SAMPLE_JSON = b'[{"name":"alpha","value":1},{"name":"beta","value":2}]\n'


@pytest.mark.asyncio
async def test_json_upload_ingest(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session,
    memory_storage,
    stub_celery_delay,
) -> None:
    from app.services.ingest.ingest_service import IngestService

    dataset_id = await _create_dataset(client, auth_headers)
    upload_response = await client.post(
        f"/api/v1/datasets/{dataset_id}/upload",
        headers=auth_headers,
        files={"file": ("sample.json", io.BytesIO(SAMPLE_JSON), "application/json")},
    )
    assert upload_response.status_code == 202

    tenant_id, queued_dataset_id, storage_key, filename, *_rest = stub_celery_delay["args"]
    publisher_id = _rest[1] if len(_rest) > 1 else None
    await IngestService().run(
        tenant_id=uuid.UUID(str(tenant_id)),
        dataset_id=uuid.UUID(str(queued_dataset_id)),
        storage_key=str(storage_key),
        filename=str(filename),
        publisher_id=uuid.UUID(str(publisher_id)) if publisher_id else None,
    )

    get_response = await client.get(f"/api/v1/datasets/{dataset_id}", headers=auth_headers)
    data = get_response.json()["data"]
    assert data["row_count"] == 2
    assert len(data["schema_snapshot"]["columns"]) == 2
