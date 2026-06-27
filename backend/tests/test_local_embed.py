"""Hash-based dev embedding fallback when sentence-transformers is unavailable."""

import pytest

from app.services.ai.llm_provider import _local_embed


@pytest.mark.asyncio
async def test_local_embed_hash_fallback_returns_384_dimensions() -> None:
    vector = await _local_embed("renewable energy capacity")
    assert len(vector) == 384
    assert all(-1.0 <= value <= 1.0 for value in vector)

    same = await _local_embed("renewable energy capacity")
    different = await _local_embed("unrelated topic")
    assert same == vector
    assert different != vector
