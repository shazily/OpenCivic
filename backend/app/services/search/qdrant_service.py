"""Qdrant vector search — degrades gracefully when unavailable or unindexed."""

from __future__ import annotations

import uuid

import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


async def verify_qdrant_connection() -> None:
    """Ping Qdrant REST API. Raises on connection failure."""
    import httpx

    if not settings.QDRANT_URL:
        raise RuntimeError("QDRANT_URL is not configured")

    headers: dict[str, str] = {}
    if settings.QDRANT_API_KEY:
        headers["api-key"] = settings.QDRANT_API_KEY
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(f"{settings.QDRANT_URL.rstrip('/')}/collections", headers=headers)
        response.raise_for_status()


async def is_semantic_search_available() -> bool:
    """Return True when Qdrant is reachable and configured."""
    if not settings.QDRANT_URL:
        return False
    try:
        await verify_qdrant_connection()
        return True
    except Exception:
        return False


def collection_name(tenant_id: uuid.UUID) -> str:
    """Per-tenant Qdrant collection name."""
    return f"tenant_{str(tenant_id).replace('-', '_')}"


async def semantic_dataset_ids(
    tenant_id: uuid.UUID,
    query: str,
    *,
    limit: int = 10,
) -> list[uuid.UUID]:
    """
    Return dataset IDs from semantic search when the tenant collection exists.
    Returns an empty list when Qdrant is down or embeddings are not indexed yet.
    """
    try:
        from qdrant_client import AsyncQdrantClient
    except ImportError:
        return []

    from app.services.ai.llm_provider import _local_embed

    client = AsyncQdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY or None,
        timeout=5,
    )
    name = collection_name(tenant_id)
    try:
        collections = await client.get_collections()
        names = {item.name for item in collections.collections}
        if name not in names:
            return []

        vector = await _local_embed(query)
        results = await client.search(
            collection_name=name,
            query_vector=vector,
            limit=limit,
        )
        ids: list[uuid.UUID] = []
        for hit in results:
            payload = hit.payload or {}
            raw_id = payload.get("dataset_id")
            if raw_id:
                ids.append(uuid.UUID(str(raw_id)))
        return ids
    except Exception as exc:
        logger.warning("qdrant_semantic_search_skipped", error=str(exc))
        return []
    finally:
        await client.close()
