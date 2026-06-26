"""Live Ollama chat pipeline — skipped when Ollama is unreachable."""

import os

import httpx
import pytest

from app.core.config import get_settings, settings
from app.services.ai.llm_pipeline import safe_complete


def _ollama_reachable() -> bool:
    base = os.environ.get("LLM_BASE_URL", settings.LLM_BASE_URL).rstrip("/")
    try:
        response = httpx.get(f"{base}/api/tags", timeout=3.0)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


@pytest.mark.asyncio
@pytest.mark.skipif(not _ollama_reachable(), reason="Ollama not reachable")
async def test_ollama_safe_complete_live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_MODE", "assist")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    get_settings.cache_clear()

    result = await safe_complete(
        data_content="region: string\npopulation: integer\nrow_count: 100",
        user_question="In one short sentence, what columns does this dataset have?",
        max_tokens=64,
    )
    assert result.content.strip()
    assert result.model == settings.LLM_MODEL
