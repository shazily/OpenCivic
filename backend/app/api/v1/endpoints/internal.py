"""Internal service endpoints — TUS hooks, not for public clients."""

from __future__ import annotations

import hashlib

import structlog
from fastapi import APIRouter, Header, Request, Response
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.errors import AuthenticationRequired
from app.services.auth.gateway_auth import evaluate_gateway_auth

router = APIRouter()
logger = structlog.get_logger(__name__)


class TusHookPayload(BaseModel):
    """Minimal tusd hook payload for post-finish notifications."""

    type: str = Field(default="post-finish")
    event: dict = Field(default_factory=dict)


def _metadata_value(metadata: object, key: str) -> str | None:
    if not isinstance(metadata, dict):
        return None
    value = metadata.get(key)
    if value is None:
        return None
    return str(value)


class BackupVerifiedPayload(BaseModel):
    """Report from pgBackRest verify CronJob."""

    status: str = Field(pattern=r"^(ok|failed)$")
    message: str = Field(default="", max_length=2000)
    verified_at: str | None = None


@router.api_route("/gateway-auth", methods=["GET", "HEAD"])
async def gateway_auth(
    request: Request,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-Api-Key"),
    x_forwarded_uri: str | None = Header(default=None, alias="X-Forwarded-Uri"),
    x_forwarded_method: str | None = Header(default=None, alias="X-Forwarded-Method"),
) -> Response:
    """APISIX forward-auth hook — validates JWT/API keys and returns trusted identity headers."""
    uri = x_forwarded_uri or str(request.url.path)
    method = x_forwarded_method or request.method
    status_code, headers = await evaluate_gateway_auth(
        method,
        uri,
        authorization,
        x_api_key,
        client_fingerprint=request.client.host if request.client else None,
    )
    return Response(status_code=status_code, headers=headers)


@router.post("/backup-verified")
async def backup_verified_hook(
    body: BackupVerifiedPayload,
    x_backup_verify_secret: str | None = Header(default=None, alias="X-Backup-Verify-Secret"),
) -> dict:
    """Receive backup verification result from Helm CronJob or sidecar."""
    secret = settings.BACKUP_VERIFY_HOOK_SECRET
    if not secret or x_backup_verify_secret != secret:
        raise AuthenticationRequired(message="Invalid backup verify secret.")

    import json
    from datetime import UTC, datetime

    from app.core.cache import cache_set
    from app.services.platform.backup_status import BACKUP_STATUS_KEY

    verified_at = body.verified_at or datetime.now(UTC).isoformat()
    payload = {
        "status": body.status,
        "verified_at": verified_at,
        "message": body.message,
    }
    await cache_set(BACKUP_STATUS_KEY, json.dumps(payload), ttl_seconds=604_800)
    return {"data": payload, "meta": {}, "errors": []}


@router.post("/tus-hook")
async def tus_upload_hook(
    body: TusHookPayload,
    x_tus_hook_secret: str | None = Header(default=None, alias="X-Tus-Hook-Secret"),
) -> dict:
    """
    Receive tusd post-finish hook. Copies upload to Minio and queues ingest when metadata is present.
    """
    secret = settings.TUS_HOOK_SECRET
    if not secret or x_tus_hook_secret != secret:
        raise AuthenticationRequired(message="Invalid TUS hook secret.")

    upload_info = body.event.get("Upload", {})
    upload_id = upload_info.get("ID")
    metadata = upload_info.get("MetaData") or upload_info.get("Metadata") or {}
    tenant_id = _metadata_value(metadata, "tenant_id")
    dataset_id = _metadata_value(metadata, "dataset_id")
    storage_key = _metadata_value(metadata, "storage_key")
    filename = _metadata_value(metadata, "filename") or "upload.bin"
    publisher_id = _metadata_value(metadata, "publisher_id")

    copied = False
    ingest_queued = False
    job_id: str | None = None

    if tenant_id and dataset_id and storage_key and upload_id:
        from app.services.ingest.tus_upload_service import TusUploadService
        from app.services.storage.storage_client import get_storage_client
        from app.workers.tasks.tasks import process_upload

        storage = get_storage_client()
        if not await storage.exists(storage_key):
            await TusUploadService().copy_upload_to_storage(
                str(upload_id),
                storage_key,
                filename,
            )
            copied = True

        idempotency_key = hashlib.sha256(
            f"tus:{dataset_id}:{storage_key}".encode()
        ).hexdigest()
        task = process_upload.delay(
            tenant_id,
            dataset_id,
            storage_key,
            filename,
            idempotency_key,
            publisher_id,
        )
        ingest_queued = True
        job_id = task.id
        logger.info(
            "tus_ingest_queued",
            dataset_id=dataset_id,
            storage_key=storage_key,
            job_id=job_id,
            copied=copied,
        )

    logger.info(
        "tus_upload_finished",
        hook_type=body.type,
        upload_id=upload_id,
        size=upload_info.get("Size"),
        ingest_queued=ingest_queued,
    )
    return {
        "data": {
            "accepted": True,
            "hook_type": body.type,
            "copied_to_storage": copied,
            "ingest_queued": ingest_queued,
            "job_id": job_id,
        },
        "meta": {},
        "errors": [],
    }
