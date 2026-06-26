"""Full TUS upload flow against live tusd — skipped when tusd is not running."""

import base64
import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core.config import settings
from app.services.ingest.tus_upload_service import TusUploadService


def _tusd_reachable() -> bool:
    base = settings.TUS_INTERNAL_URL.rstrip("/")
    try:
        response = httpx.get(f"{base}/", timeout=3.0, follow_redirects=True)
        return response.status_code < 500
    except httpx.HTTPError:
        return False


def _encode_metadata(meta: dict[str, str]) -> str:
    return ",".join(
        f"{key} {base64.b64encode(value.encode()).decode()}"
        for key, value in meta.items()
    )


@pytest.mark.asyncio
@pytest.mark.skipif(not _tusd_reachable(), reason="tusd not reachable")
async def test_tus_upload_copy_e2e(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST + PATCH to tusd, then copy into object storage via TusUploadService."""
    del monkeypatch
    base = settings.TUS_INTERNAL_URL.rstrip("/")
    payload = b"region,population\nNorth,100\nSouth,200\n"
    upload_id = uuid.uuid4().hex

    create = httpx.post(
        base,
        headers={
            "Tus-Resumable": "1.0.0",
            "Upload-Length": str(len(payload)),
            "Upload-Metadata": _encode_metadata(
                {
                    "filename": "regions.csv",
                    "dataset_id": "00000000-0000-0000-0000-000000000099",
                }
            ),
        },
        timeout=10.0,
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
        content=payload,
        timeout=10.0,
    )
    assert patch.status_code == 204

    tus_upload_id = location.rstrip("/").split("/")[-1]
    storage_key = f"raw/e2e/{upload_id}/regions.csv"

    mock_storage = AsyncMock()
    mock_storage.ensure_bucket = AsyncMock()
    mock_storage.put = AsyncMock(return_value=storage_key)

    with patch("app.services.ingest.tus_upload_service.get_storage_client", return_value=mock_storage):
        size = await TusUploadService().copy_upload_to_storage(
            tus_upload_id,
            storage_key,
            "regions.csv",
        )

    assert size == len(payload)
    mock_storage.put.assert_awaited_once()
    put_args = mock_storage.put.await_args
    assert put_args.args[1] == payload
