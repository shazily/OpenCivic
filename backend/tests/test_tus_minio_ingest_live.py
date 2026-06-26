"""Live TUS → Minio → ingest chain — no storage mocks."""

import base64
import os
import time
import uuid

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import settings

SAMPLE_CSV = b"name,value\nalpha,1\nbeta,2\n"


def _tusd_reachable() -> bool:
    base = settings.TUS_INTERNAL_URL.rstrip("/")
    try:
        response = httpx.get(f"{base}/", timeout=3.0, follow_redirects=True)
        return response.status_code < 500
    except httpx.HTTPError:
        return False


def _minio_reachable() -> bool:
    endpoint = settings.MINIO_ENDPOINT.rstrip("/")
    try:
        response = httpx.get(f"{endpoint}/minio/health/live", timeout=3.0)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


def _encode_metadata(meta: dict[str, str]) -> str:
    return ",".join(
        f"{key} {base64.b64encode(value.encode()).decode()}"
        for key, value in meta.items()
    )


@pytest.mark.live
@pytest.mark.asyncio
@pytest.mark.skipif(not _tusd_reachable(), reason="tusd not reachable")
@pytest.mark.skipif(not _minio_reachable(), reason="Minio not reachable")
async def test_tus_minio_ingest_full_chain(
    client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """tusd upload → hook → real Minio → ingest updates dataset."""
    monkeypatch.setattr("app.core.config.settings.TUS_ENABLED", True)
    monkeypatch.setattr("app.core.config.settings.TUS_HOOK_SECRET", "test-tus-hook-secret")

    slug = f"tus-live-{uuid.uuid4().hex[:8]}"
    created = await client.post(
        "/api/v1/datasets/",
        headers=auth_headers,
        json={"title": "TUS Minio Live", "slug": slug},
    )
    assert created.status_code == 201
    dataset_id = created.json()["data"]["id"]
    tenant_id = os.environ["DEV_TENANT_ID"]
    publisher_id = os.environ["DEV_USER_ID"]
    storage_key = f"raw/{tenant_id}/{dataset_id}/upload.csv"

    session_resp = await client.post(
        f"/api/v1/datasets/{dataset_id}/upload/tus-session",
        headers=auth_headers,
        json={"filename": "upload.csv"},
    )
    assert session_resp.status_code == 201
    tus_meta = session_resp.json()["data"]["upload_metadata"]

    base = settings.TUS_INTERNAL_URL.rstrip("/")
    create = httpx.post(
        base,
        headers={
            "Tus-Resumable": "1.0.0",
            "Upload-Length": str(len(SAMPLE_CSV)),
            "Upload-Metadata": _encode_metadata(tus_meta),
        },
        timeout=30.0,
    )
    assert create.status_code == 201
    location = create.headers.get("Location", "")
    assert location

    patch = httpx.patch(
        location,
        headers={
            "Tus-Resumable": "1.0.0",
            "Upload-Offset": "0",
            "Content-Type": "application/offset+octet-stream",
        },
        content=SAMPLE_CSV,
        timeout=30.0,
    )
    assert patch.status_code == 204

    row_count = None
    for _ in range(60):
        polled = await client.get(f"/api/v1/datasets/{dataset_id}", headers=auth_headers)
        polled.raise_for_status()
        row_count = polled.json()["data"].get("row_count")
        if row_count:
            break
        time.sleep(1)

    assert row_count == 2, "Ingest did not complete — check tusd hook and worker"

    from app.db.models import Event
    from app.db.session import tenant_write_session

    async with tenant_write_session(uuid.UUID(tenant_id)) as session:
        event = await session.scalar(
            select(Event).where(
                Event.aggregate_id == uuid.UUID(dataset_id),
                Event.event_type == "DatasetIngested",
            )
        )
        assert event is not None

    from app.services.storage.storage_client import get_storage_client

    storage = get_storage_client()
    assert await storage.exists(storage_key)
