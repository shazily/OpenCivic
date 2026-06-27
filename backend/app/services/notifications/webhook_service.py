"""Webhook delivery — HMAC-signed HTTP POST to subscriber URLs."""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid

import httpx
import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt
from app.db.models import Webhook

logger = structlog.get_logger(__name__)

WEBHOOK_TIMEOUT_SECONDS = 10


def sign_payload(secret: str, body: bytes) -> str:
    """Return hex HMAC-SHA256 signature for webhook body."""
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def deliver_webhook_http(
    *,
    url: str,
    secret: str,
    event_type: str,
    payload: dict,
) -> tuple[int, str]:
    """POST signed webhook payload. Returns status code and response snippet."""
    envelope = {
        "event_type": event_type,
        "payload": payload,
    }
    body = json.dumps(envelope, separators=(",", ":"), sort_keys=True).encode()
    signature = sign_payload(secret, body)
    headers = {
        "Content-Type": "application/json",
        "X-OpenCivic-Event": event_type,
        "X-OpenCivic-Signature": f"sha256={signature}",
    }
    async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT_SECONDS) as client:
        response = await client.post(url, content=body, headers=headers)
    snippet = response.text[:200] if response.text else ""
    return response.status_code, snippet


async def deliver_webhook_by_id(
    session: AsyncSession,
    webhook_id: uuid.UUID,
    event_type: str,
    payload: dict,
) -> dict:
    """Load webhook, deliver, update delivery metadata."""
    webhook = await session.scalar(select(Webhook).where(Webhook.id == webhook_id))
    if webhook is None:
        return {"status": "not_found", "webhook_id": str(webhook_id)}
    if webhook.status != "active":
        return {"status": "inactive", "webhook_id": str(webhook_id)}

    secret = decrypt(webhook.secret)
    try:
        status_code, snippet = await deliver_webhook_http(
            url=webhook.url,
            secret=secret,
            event_type=event_type,
            payload=payload,
        )
    except httpx.HTTPError as exc:
        await session.execute(
            update(Webhook)
            .where(Webhook.id == webhook_id)
            .values(failure_count=Webhook.failure_count + 1)
        )
        logger.warning(
            "webhook_delivery_failed",
            webhook_id=str(webhook_id),
            error=str(exc),
        )
        return {"status": "error", "webhook_id": str(webhook_id), "error": str(exc)}

    if status_code >= 400:
        await session.execute(
            update(Webhook)
            .where(Webhook.id == webhook_id)
            .values(failure_count=Webhook.failure_count + 1)
        )
        return {
            "status": "http_error",
            "webhook_id": str(webhook_id),
            "status_code": status_code,
            "body": snippet,
        }

    from datetime import UTC, datetime

    await session.execute(
        update(Webhook)
        .where(Webhook.id == webhook_id)
        .values(
            last_delivery_at=datetime.now(UTC),
            failure_count=0,
        )
    )
    return {"status": "ok", "webhook_id": str(webhook_id), "status_code": status_code}


async def enqueue_matching_webhooks(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    event_type: str,
    dataset_id: uuid.UUID,
    payload: dict,
) -> int:
    """Find active webhooks subscribed to event_type and queue Celery deliveries."""
    from sqlalchemy import or_, select

    result = await session.scalars(
        select(Webhook).where(
            Webhook.tenant_id == tenant_id,
            Webhook.status == "active",
            or_(Webhook.dataset_id.is_(None), Webhook.dataset_id == dataset_id),
        )
    )
    webhooks = [item for item in result.all() if event_type in item.events]
    if not webhooks:
        return 0

    from app.workers.tasks.tasks import deliver_webhook as deliver_webhook_task

    delivery_payload = {
        **payload,
        "dataset_id": str(dataset_id),
        "tenant_id": str(tenant_id),
    }
    for webhook in webhooks:
        deliver_webhook_task.delay(str(webhook.id), event_type, delivery_payload)
    return len(webhooks)
