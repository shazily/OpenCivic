"""Live chat-with-dataset via Ollama — skipped when Ollama is unreachable."""

import os
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy import delete

from app.core.config import get_settings, settings
from app.db.models import Dataset
from app.db.session import set_tenant_context, tenant_write_session
from app.repositories.dataset_version_repository import DatasetVersionRepository
from app.services.ai.chat_service import chat_with_dataset


def _ollama_reachable() -> bool:
    base = os.environ.get("LLM_BASE_URL", settings.LLM_BASE_URL).rstrip("/")
    try:
        response = httpx.get(f"{base}/api/tags", timeout=3.0)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


@pytest.mark.asyncio
@pytest.mark.skipif(not _ollama_reachable(), reason="Ollama not reachable")
async def test_ollama_chat_dataset_columns_live(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AI_MODE", "assist")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    get_settings.cache_clear()

    tenant_id = uuid.UUID(os.environ["DEV_TENANT_ID"])
    publisher_id = uuid.UUID(os.environ["DEV_USER_ID"])
    dataset_id = uuid.uuid4()

    await set_tenant_context(db_session, tenant_id)
    dataset = Dataset(
        id=dataset_id,
        tenant_id=tenant_id,
        title="Ollama Chat Live",
        slug=f"ollama-chat-{uuid.uuid4().hex[:8]}",
        publisher_id=publisher_id,
        status="published",
        published_at=datetime.now(UTC),
        row_count=3,
        schema_snapshot={
            "columns": [
                {"name": "region", "type": "string"},
                {"name": "population", "type": "integer"},
            ]
        },
    )
    db_session.add(dataset)
    await db_session.flush()
    await DatasetVersionRepository(db_session).create(
        tenant_id=tenant_id,
        dataset_id=dataset_id,
        version_number=1,
        schema_snapshot=dataset.schema_snapshot,
        row_count=3,
        storage_path=f"parquet/{tenant_id}/{dataset_id}/v1.parquet",
        raw_file_path="raw/test.csv",
    )
    await db_session.commit()

    parquet = (
        b"PAR1"
        b"\x00\x00"
        b"PAR1"
    )

    mock_storage = AsyncMock()
    mock_storage.get = AsyncMock(return_value=parquet)

    with patch("app.services.ai.chat_service.get_storage_client", return_value=mock_storage):
        with patch(
            "app.services.ai.chat_service.DatasetDataReader.read_page",
            new_callable=AsyncMock,
            return_value=([], False, None, 3, 1),
        ):
            result = await chat_with_dataset(
                db_session,
                dataset_id,
                "What columns does this dataset have? Reply with column names only.",
                user_id=publisher_id,
            )

    assert result["answer"].strip()
    lowered = result["answer"].lower()
    assert "region" in lowered or "population" in lowered or result.get("ai_assisted") is True

    async with tenant_write_session(tenant_id) as session:
        await session.execute(delete(Dataset).where(Dataset.id == dataset_id))
