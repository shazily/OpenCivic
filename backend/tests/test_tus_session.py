"""TUS session and finalize service tests."""

import os
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.services.ingest.tus_upload_service import TusUploadService


@pytest.mark.asyncio
async def test_tus_session_requires_enabled(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    created = await client.post(
        "/api/v1/datasets/",
        headers=auth_headers,
        json={"title": "TUS Test", "slug": f"tus-test-{uuid.uuid4().hex[:8]}"},
    )
    dataset_id = created.json()["data"]["id"]
    response = await client.post(
        f"/api/v1/datasets/{dataset_id}/upload/tus-session",
        headers=auth_headers,
        json={"filename": "sample.csv"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_tus_session_returns_metadata(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.config.settings.TUS_ENABLED", True)
    slug = f"tus-session-{uuid.uuid4().hex[:8]}"
    created = await client.post(
        "/api/v1/datasets/",
        headers=auth_headers,
        json={"title": "TUS Session", "slug": slug},
    )
    dataset_id = created.json()["data"]["id"]
    response = await client.post(
        f"/api/v1/datasets/{dataset_id}/upload/tus-session",
        headers=auth_headers,
        json={"filename": "sample.csv"},
    )
    assert response.status_code == 201
    body = response.json()["data"]
    assert body["endpoint"].endswith("/files/")
    assert body["storage_key"].startswith("raw/")
    assert body["upload_metadata"]["dataset_id"] == dataset_id
    assert body["upload_metadata"]["filename"] == "sample.csv"


@pytest.mark.asyncio
async def test_tus_copy_upload_to_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.config.settings.TUS_INTERNAL_URL", "http://tusd:1080/files/")
    monkeypatch.setattr("app.core.config.settings.MINIO_BUCKET", "opencivic")

    mock_storage = AsyncMock()
    mock_storage.ensure_bucket = AsyncMock()
    mock_storage.put = AsyncMock(return_value="raw/key.csv")

    mock_response = AsyncMock()
    mock_response.raise_for_status = lambda: None
    mock_response.content = b"col1,col2\n1,2"

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.ingest.tus_upload_service.get_storage_client", return_value=mock_storage):
        with patch("app.services.ingest.tus_upload_service.httpx.AsyncClient", return_value=mock_client):
            size = await TusUploadService().copy_upload_to_storage(
                "upload-abc",
                "raw/tenant/dataset/upload.csv",
                "upload.csv",
            )

    assert size == 13
    mock_storage.put.assert_awaited_once()
