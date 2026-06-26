"""Live Minio reachability — skipped when Minio is not running."""

import httpx
import pytest

from app.core.config import settings


def _minio_reachable() -> bool:
    endpoint = settings.MINIO_ENDPOINT.rstrip("/")
    try:
        response = httpx.get(f"{endpoint}/minio/health/live", timeout=3.0)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


@pytest.mark.live
@pytest.mark.skipif(not _minio_reachable(), reason="Minio not reachable")
@pytest.mark.asyncio
async def test_minio_put_and_get_roundtrip() -> None:
    """Exercise real Minio storage client when compose Minio is up."""
    from app.services.storage.storage_client import get_storage_client

    storage = get_storage_client()
    bucket = settings.MINIO_BUCKET
    key = "pytest/minio-live-roundtrip.txt"
    payload = b"opencivic-minio-live-test"

    await storage.ensure_bucket(bucket)
    await storage.put(key, payload, content_type="text/plain")
    downloaded = await storage.get(key)
    assert downloaded == payload
