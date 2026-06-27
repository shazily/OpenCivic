"""TUS hook → storage copy → ingest pipeline E2E (real IngestService, in-memory storage)."""

import os
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

SAMPLE_CSV = b"name,value\nalpha,1\nbeta,2\n"


@pytest.fixture
def tus_ingest_storage(monkeypatch: pytest.MonkeyPatch):
    """Wire in-memory storage across hook, copy, and ingest paths."""
    from tests.fakes.memory_storage import MemoryStorageClient

    storage = MemoryStorageClient()
    targets = (
        "app.services.storage.storage_client.get_storage_client",
        "app.services.ingest.tus_upload_service.get_storage_client",
        "app.services.ingest.ingest_service.get_storage_client",
    )
    for target in targets:
        monkeypatch.setattr(target, lambda: storage)
    return storage


@pytest.mark.asyncio
async def test_tus_hook_copies_and_ingests_csv(
    client: AsyncClient,
    auth_headers: dict[str, str],
    tus_ingest_storage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hook copies upload to storage and eager Celery ingest updates the dataset."""
    from app.services.ingest.tus_upload_service import TusUploadService

    monkeypatch.setattr("app.core.config.settings.TUS_HOOK_SECRET", "test-tus-hook-secret")
    monkeypatch.setattr("app.core.config.settings.MINIO_BUCKET", "opencivic-test")

    created = await client.post(
        "/api/v1/datasets/",
        headers=auth_headers,
        json={"title": "TUS Hook Ingest", "slug": f"tus-hook-{uuid.uuid4().hex[:8]}"},
    )
    assert created.status_code == 201
    dataset_id = created.json()["data"]["id"]
    tenant_id = os.environ["DEV_TENANT_ID"]
    publisher_id = os.environ["DEV_USER_ID"]
    storage_key = f"raw/{tenant_id}/{dataset_id}/upload.csv"

    async def fake_copy(_self, _upload_id: str, key: str, _filename: str) -> int:
        await tus_ingest_storage.ensure_bucket("opencivic-test")
        await tus_ingest_storage.put(key, SAMPLE_CSV, content_type="text/csv")
        return len(SAMPLE_CSV)

    monkeypatch.setattr(TusUploadService, "copy_upload_to_storage", fake_copy)

    captured: dict[str, tuple] = {}

    class FakeAsyncResult:
        id = "tus-ingest-job"

    def capture_delay(*args: object, **kwargs: object) -> FakeAsyncResult:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return FakeAsyncResult()

    monkeypatch.setattr("app.workers.tasks.tasks.process_upload.delay", capture_delay)

    hook_response = await client.post(
        "/api/v1/internal/tus-hook",
        json={
            "type": "post-finish",
            "event": {
                "Upload": {
                    "ID": "upload-hook-e2e",
                    "MetaData": {
                        "tenant_id": tenant_id,
                        "dataset_id": dataset_id,
                        "storage_key": storage_key,
                        "filename": "upload.csv",
                        "publisher_id": publisher_id,
                    },
                }
            },
        },
        headers={"X-Tus-Hook-Secret": "test-tus-hook-secret"},
    )
    assert hook_response.status_code == 200
    hook_body = hook_response.json()["data"]
    assert hook_body["ingest_queued"] is True
    assert hook_body["copied_to_storage"] is True
    assert storage_key in tus_ingest_storage.objects
    assert "args" in captured

    from app.services.ingest.ingest_service import IngestService

    tenant_arg, dataset_arg, key_arg, filename_arg, *_rest = captured["args"]
    publisher_arg = _rest[1] if len(_rest) > 1 else None
    await IngestService().run(
        tenant_id=uuid.UUID(str(tenant_arg)),
        dataset_id=uuid.UUID(str(dataset_arg)),
        storage_key=str(key_arg),
        filename=str(filename_arg),
        publisher_id=uuid.UUID(str(publisher_arg)) if publisher_arg else None,
    )

    get_response = await client.get(f"/api/v1/datasets/{dataset_id}", headers=auth_headers)
    assert get_response.status_code == 200
    data = get_response.json()["data"]
    assert data["row_count"] == 2
    assert data["schema_snapshot"] is not None

    from app.db.models import DatasetVersion, Event
    from app.db.session import tenant_write_session

    async with tenant_write_session(uuid.UUID(tenant_id)) as session:
        version = await session.scalar(
            select(DatasetVersion).where(DatasetVersion.dataset_id == uuid.UUID(dataset_id))
        )
        assert version is not None
        assert version.row_count == 2
        event = await session.scalar(
            select(Event).where(
                Event.aggregate_id == uuid.UUID(dataset_id),
                Event.event_type == "DatasetIngested",
            )
        )
        assert event is not None
