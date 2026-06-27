"""Finalize tusd uploads — copy completed files into object storage."""

from __future__ import annotations

import mimetypes

import httpx
import structlog

from app.core.config import settings
from app.services.storage.storage_client import get_storage_client

logger = structlog.get_logger(__name__)


class TusUploadService:
    """Copy a completed tusd upload into Minio and return byte size."""

    async def copy_upload_to_storage(
        self,
        upload_id: str,
        storage_key: str,
        filename: str,
    ) -> int:
        """Download from tusd and store at storage_key. Returns uploaded byte count."""
        base = settings.TUS_INTERNAL_URL.rstrip("/")
        url = f"{base}/{upload_id}"

        async with httpx.AsyncClient(timeout=600.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            content = response.content

        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        storage = get_storage_client()
        await storage.ensure_bucket(settings.MINIO_BUCKET)
        await storage.put(storage_key, content, content_type=content_type)
        logger.info(
            "tus_copied_to_storage",
            upload_id=upload_id,
            storage_key=storage_key,
            bytes=len(content),
        )
        return len(content)
