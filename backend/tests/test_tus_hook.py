"""TUS internal hook endpoint tests."""

import os

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_tus_hook_rejects_missing_secret(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/internal/tus-hook",
        json={"type": "post-finish", "event": {"Upload": {"ID": "abc"}}},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_tus_hook_accepts_valid_secret(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.config.settings.TUS_HOOK_SECRET", "test-tus-hook-secret")
    response = await client.post(
        "/api/v1/internal/tus-hook",
        json={"type": "post-finish", "event": {"Upload": {"ID": "abc", "Size": 1024}}},
        headers={"X-Tus-Hook-Secret": "test-tus-hook-secret"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["accepted"] is True
    assert response.json()["data"]["ingest_queued"] is False


@pytest.mark.asyncio
async def test_tus_hook_queues_ingest_with_metadata(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import AsyncMock, MagicMock

    monkeypatch.setattr("app.core.config.settings.TUS_HOOK_SECRET", "test-tus-hook-secret")
    mock_delay = MagicMock()
    mock_delay.return_value.id = "job-123"
    monkeypatch.setattr("app.workers.tasks.tasks.process_upload.delay", mock_delay)

    mock_storage = AsyncMock()
    mock_storage.exists = AsyncMock(return_value=False)
    monkeypatch.setattr(
        "app.services.storage.storage_client.get_storage_client",
        lambda: mock_storage,
    )
    mock_copy = AsyncMock(return_value=12)
    monkeypatch.setattr(
        "app.services.ingest.tus_upload_service.TusUploadService.copy_upload_to_storage",
        mock_copy,
    )

    response = await client.post(
        "/api/v1/internal/tus-hook",
        json={
            "type": "post-finish",
            "event": {
                "Upload": {
                    "ID": "upload-abc",
                    "MetaData": {
                        "tenant_id": "00000000-0000-0000-0000-000000000001",
                        "dataset_id": "00000000-0000-0000-0000-000000000099",
                        "storage_key": "raw/tus/upload.csv",
                        "filename": "upload.csv",
                    },
                }
            },
        },
        headers={"X-Tus-Hook-Secret": "test-tus-hook-secret"},
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["ingest_queued"] is True
    assert body["copied_to_storage"] is True
    assert body["job_id"] == "job-123"
    mock_copy.assert_awaited_once()
    mock_delay.assert_called_once()
