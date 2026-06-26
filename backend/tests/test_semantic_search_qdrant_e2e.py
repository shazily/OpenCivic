"""Semantic search E2E against Qdrant when the service is available."""

import os
import uuid
from unittest.mock import patch

import httpx
import pytest

from app.core.config import settings
from app.services.search.qdrant_index_service import index_published_dataset
from app.services.search.qdrant_service import semantic_dataset_ids, verify_qdrant_connection

_DEV_VECTOR = [0.42] * 384


def _qdrant_client_available() -> bool:
    try:
        from qdrant_client import AsyncQdrantClient  # noqa: F401

        return True
    except ImportError:
        return False


def _qdrant_reachable() -> bool:
    try:
        headers: dict[str, str] = {}
        if settings.QDRANT_API_KEY:
            headers["api-key"] = settings.QDRANT_API_KEY
        response = httpx.get(
            f"{settings.QDRANT_URL.rstrip('/')}/collections",
            headers=headers,
            timeout=3.0,
        )
        return response.status_code == 200
    except httpx.HTTPError:
        return False


@pytest.mark.asyncio
@pytest.mark.skipif(not _qdrant_reachable(), reason="Qdrant not reachable")
async def test_qdrant_connection() -> None:
    await verify_qdrant_connection()


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _qdrant_reachable() or not _qdrant_client_available(),
    reason="Qdrant or qdrant-client unavailable",
)
async def test_semantic_search_finds_indexed_dataset(db_session) -> None:
    from app.db.models import Dataset
    from app.db.session import set_tenant_context

    tenant_id = uuid.UUID(os.environ["DEV_TENANT_ID"])
    publisher_id = uuid.UUID(os.environ["DEV_USER_ID"])
    unique = uuid.uuid4().hex[:8]
    await set_tenant_context(db_session, tenant_id)
    dataset = Dataset(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        title=f"Renewable Energy Capacity {unique}",
        slug=f"renewable-{unique}",
        description="Installed solar and wind capacity by region",
        status="published",
        access_level="public",
        publisher_id=publisher_id,
        tags=["energy", "climate"],
    )
    db_session.add(dataset)
    await db_session.commit()
    await db_session.refresh(dataset)

    async def fixed_embed(_text: str) -> list[float]:
        return _DEV_VECTOR

    with (
        patch("app.services.search.qdrant_index_service._local_embed", new=fixed_embed),
        patch("app.services.ai.llm_provider._local_embed", new=fixed_embed),
    ):
        result = await index_published_dataset(dataset)
        assert result["status"] == "indexed", result

        from qdrant_client import AsyncQdrantClient
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        from app.services.search.qdrant_service import collection_name

        qdrant = AsyncQdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY or None,
            timeout=5,
        )
        try:
            points, _ = await qdrant.scroll(
                collection_name=collection_name(tenant_id),
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="dataset_id",
                            match=MatchValue(value=str(dataset.id)),
                        )
                    ]
                ),
                limit=1,
            )
            assert points, "dataset vector not present in Qdrant"
        finally:
            await qdrant.close()

        ids = await semantic_dataset_ids(
            tenant_id,
            f"Renewable Energy Capacity {unique}",
            limit=50,
        )
    assert dataset.id in ids
