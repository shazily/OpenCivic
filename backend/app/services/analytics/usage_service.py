"""Record usage events with optional Valkey counters."""

from __future__ import annotations

import uuid

import structlog

from app.core.cache import cache_incr
from app.db.session import tenant_write_session
from app.repositories.usage_event_repository import UsageEventRepository

logger = structlog.get_logger(__name__)


def _cache_key(tenant_id: uuid.UUID, dataset_id: uuid.UUID, event_type: str) -> str:
    return f"usage:{tenant_id}:{dataset_id}:{event_type}"


async def record_usage_event(
    *,
    tenant_id: uuid.UUID,
    dataset_id: uuid.UUID,
    event_type: str,
    actor_id: uuid.UUID | None = None,
    api_key_id: uuid.UUID | None = None,
    format_name: str | None = None,
    bytes_count: int | None = None,
    response_ms: int | None = None,
) -> None:
    """Persist a usage event and increment the Valkey counter when available."""
    try:
        async with tenant_write_session(tenant_id) as session:
            await UsageEventRepository(session).record(
                tenant_id=tenant_id,
                event_type=event_type,
                dataset_id=dataset_id,
                actor_id=actor_id,
                api_key_id=api_key_id,
                format_name=format_name,
                bytes_count=bytes_count,
                response_ms=response_ms,
            )
            await session.commit()
    except Exception as exc:
        logger.warning("usage_event_persist_failed", error=str(exc), dataset_id=str(dataset_id))
        return

    try:
        await cache_incr(_cache_key(tenant_id, dataset_id, event_type))
    except Exception as exc:
        logger.warning("usage_cache_incr_failed", error=str(exc))
