"""Resumable chunked upload sessions backed by Valkey and Minio."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from app.core.cache import cache_get, cache_set
from app.core.config import settings
from app.core.errors import NotFound, ValidationError
from app.services.storage.storage_client import StorageClient, get_storage_client

CHUNK_SIZE_BYTES = 5 * 1024 * 1024
SESSION_TTL_SECONDS = 3600


@dataclass(frozen=True)
class UploadSession:
    """In-progress chunked upload metadata."""

    session_id: uuid.UUID
    tenant_id: uuid.UUID
    dataset_id: uuid.UUID
    filename: str
    extension: str
    total_size: int
    total_chunks: int
    received_chunks: int
    publisher_id: uuid.UUID


def _session_key(tenant_id: uuid.UUID, session_id: uuid.UUID) -> str:
    return f"upload_session:{tenant_id}:{session_id}"


def _chunk_key(
    tenant_id: uuid.UUID,
    dataset_id: uuid.UUID,
    session_id: uuid.UUID,
    chunk_index: int,
) -> str:
    return f"tenants/{tenant_id}/datasets/{dataset_id}/chunks/{session_id}/{chunk_index}.part"


class ChunkedUploadService:
    """Manage chunked uploads and merge parts into a single raw object."""

    def __init__(self, storage: StorageClient | None = None) -> None:
        self._storage = storage or get_storage_client()

    async def create_session(
        self,
        *,
        tenant_id: uuid.UUID,
        dataset_id: uuid.UUID,
        publisher_id: uuid.UUID,
        filename: str,
        extension: str,
        total_size: int,
    ) -> UploadSession:
        if total_size <= 0:
            raise ValidationError(message="total_size must be positive.", field="total_size")
        if total_size > settings.UPLOAD_MAX_BYTES:
            raise ValidationError(message="File exceeds maximum upload size.", field="total_size")

        total_chunks = (total_size + CHUNK_SIZE_BYTES - 1) // CHUNK_SIZE_BYTES
        session_id = uuid.uuid4()
        payload = {
            "tenant_id": str(tenant_id),
            "dataset_id": str(dataset_id),
            "publisher_id": str(publisher_id),
            "filename": filename,
            "extension": extension,
            "total_size": total_size,
            "total_chunks": total_chunks,
            "received_chunks": 0,
        }
        await cache_set(
            _session_key(tenant_id, session_id),
            json.dumps(payload),
            ttl_seconds=SESSION_TTL_SECONDS,
        )
        return UploadSession(
            session_id=session_id,
            tenant_id=tenant_id,
            dataset_id=dataset_id,
            filename=filename,
            extension=extension,
            total_size=total_size,
            total_chunks=total_chunks,
            received_chunks=0,
            publisher_id=publisher_id,
        )

    async def _load_session(self, tenant_id: uuid.UUID, session_id: uuid.UUID) -> dict:
        raw = await cache_get(_session_key(tenant_id, session_id))
        if raw is None:
            raise NotFound(message="Upload session not found or expired.")
        return json.loads(raw)

    async def store_chunk(
        self,
        *,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
        chunk_index: int,
        content: bytes,
    ) -> UploadSession:
        session = await self._load_session(tenant_id, session_id)
        if chunk_index < 0 or chunk_index >= int(session["total_chunks"]):
            raise ValidationError(message="Invalid chunk index.", field="chunk_index")

        dataset_id = uuid.UUID(session["dataset_id"])
        key = _chunk_key(tenant_id, dataset_id, session_id, chunk_index)
        await self._storage.put(key, content, content_type="application/octet-stream")

        received = int(session.get("received_chunks", 0))
        if chunk_index >= received:
            session["received_chunks"] = chunk_index + 1
        await cache_set(
            _session_key(tenant_id, session_id),
            json.dumps(session),
            ttl_seconds=SESSION_TTL_SECONDS,
        )
        return UploadSession(
            session_id=session_id,
            tenant_id=tenant_id,
            dataset_id=dataset_id,
            filename=session["filename"],
            extension=session["extension"],
            total_size=int(session["total_size"]),
            total_chunks=int(session["total_chunks"]),
            received_chunks=int(session["received_chunks"]),
            publisher_id=uuid.UUID(session["publisher_id"]),
        )

    async def complete_session(
        self,
        *,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> tuple[str, str]:
        """Merge chunk parts into the final raw upload key."""
        session = await self._load_session(tenant_id, session_id)
        total_chunks = int(session["total_chunks"])
        received = int(session.get("received_chunks", 0))
        if received < total_chunks:
            raise ValidationError(
                message=f"Missing chunks: received {received} of {total_chunks}.",
                field="chunks",
            )

        dataset_id = uuid.UUID(session["dataset_id"])
        parts: list[bytes] = []
        for index in range(total_chunks):
            key = _chunk_key(tenant_id, dataset_id, session_id, index)
            parts.append(await self._storage.get(key))

        merged = b"".join(parts)
        if len(merged) != int(session["total_size"]):
            raise ValidationError(message="Merged file size does not match declared total_size.")

        from app.services.ingest.upload_validation import raw_storage_key

        upload_id = uuid.uuid4()
        storage_key = raw_storage_key(
            tenant_id,
            dataset_id,
            upload_id,
            session["extension"],
        )
        await self._storage.put(
            storage_key,
            merged,
            content_type="application/octet-stream",
        )
        return storage_key, session["filename"]
