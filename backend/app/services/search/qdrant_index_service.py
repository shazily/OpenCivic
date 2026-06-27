"""Qdrant vector indexing for published datasets."""

from __future__ import annotations

import structlog

from app.core.config import settings
from app.db.models import Dataset
from app.services.ai.llm_provider import _local_embed
from app.services.search.qdrant_service import collection_name

logger = structlog.get_logger(__name__)

VECTOR_SIZE = 384


async def ensure_tenant_collection(client, name: str) -> None:
    from qdrant_client.http import models

    collections = await client.get_collections()
    names = {item.name for item in collections.collections}
    if name in names:
        return
    await client.create_collection(
        collection_name=name,
        vectors_config=models.VectorParams(size=VECTOR_SIZE, distance=models.Distance.COSINE),
    )


async def index_published_dataset(dataset: Dataset) -> dict[str, object]:
    """Embed title/description/tags and upsert into the tenant Qdrant collection."""
    if dataset.status != "published":
        return {"status": "skipped", "reason": "not_published"}

    try:
        from qdrant_client import AsyncQdrantClient
        from qdrant_client.http import models
    except ImportError:
        return {"status": "skipped", "reason": "qdrant_client_unavailable"}

    text = " ".join(
        part
        for part in (
            dataset.title,
            dataset.description or "",
            " ".join(dataset.tags),
        )
        if part
    )
    vector = await _local_embed(text)
    if len(vector) != VECTOR_SIZE:
        vector = vector[:VECTOR_SIZE] if len(vector) > VECTOR_SIZE else vector + [0.0] * (
            VECTOR_SIZE - len(vector)
        )

    client = AsyncQdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY or None,
        timeout=10,
    )
    name = collection_name(dataset.tenant_id)
    try:
        await ensure_tenant_collection(client, name)
        point_id = str(dataset.id)
        await client.upsert(
            collection_name=name,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "dataset_id": str(dataset.id),
                        "title": dataset.title,
                        "slug": dataset.slug,
                    },
                )
            ],
        )
        logger.info("qdrant_indexed", dataset_id=str(dataset.id))
        return {"status": "indexed", "dataset_id": str(dataset.id)}
    except Exception as exc:
        logger.warning("qdrant_index_failed", dataset_id=str(dataset.id), error=str(exc))
        return {"status": "error", "error": str(exc)}
    finally:
        await client.close()
