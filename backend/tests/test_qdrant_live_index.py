"""Qdrant indexing integration test."""

import os
import sys
import uuid
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.search.qdrant_index_service import index_published_dataset


@pytest.mark.asyncio
async def test_index_published_dataset_upserts_vector(db_session) -> None:
    """Verify published datasets upsert a vector into Qdrant."""
    from app.db.models import Dataset
    from app.db.session import set_tenant_context

    tenant_id = uuid.UUID(os.environ["DEV_TENANT_ID"])
    publisher_id = uuid.UUID(os.environ["DEV_USER_ID"])
    await set_tenant_context(db_session, tenant_id)
    dataset = Dataset(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        title="Qdrant Index Test",
        slug=f"qdrant-index-{uuid.uuid4().hex[:8]}",
        description="Semantic search indexing smoke test",
        status="published",
        access_level="public",
        publisher_id=publisher_id,
        tags=["test", "search"],
    )
    db_session.add(dataset)
    await db_session.commit()
    await db_session.refresh(dataset)

    mock_client = AsyncMock()
    mock_client.get_collections.return_value = MagicMock(collections=[])
    mock_client.create_collection = AsyncMock()
    mock_client.upsert = AsyncMock()
    mock_client.close = AsyncMock()

    mock_http = ModuleType("qdrant_client.http")
    mock_http.models = MagicMock()
    mock_http.models.PointStruct = MagicMock()
    mock_http.models.VectorParams = MagicMock()
    mock_http.models.Distance = MagicMock()
    mock_qdrant = ModuleType("qdrant_client")
    mock_qdrant.AsyncQdrantClient = MagicMock(return_value=mock_client)
    mock_qdrant.http = mock_http

    vector = [0.1] * 384
    with patch.dict(sys.modules, {"qdrant_client": mock_qdrant, "qdrant_client.http": mock_http}):
        with patch(
            "app.services.search.qdrant_index_service._local_embed",
            new_callable=AsyncMock,
            return_value=vector,
        ):
            result = await index_published_dataset(dataset)

    assert result["status"] == "indexed"
    mock_client.upsert.assert_awaited_once()
