"""Live Ollama integration — skipped when Ollama is unreachable."""

import os

import httpx
import pytest

from app.core.config import settings
from app.services.ai.llm_provider import OllamaProvider


def _ollama_reachable() -> bool:
    base = os.environ.get("LLM_BASE_URL", settings.LLM_BASE_URL).rstrip("/")
    try:
        response = httpx.get(f"{base}/api/tags", timeout=3.0)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


@pytest.mark.live
@pytest.mark.asyncio
@pytest.mark.skipif(not _ollama_reachable(), reason="Ollama not reachable")
async def test_ollama_live_complete() -> None:
    provider = OllamaProvider()
    result = await provider.complete(
        system="You are a concise assistant.",
        messages=[{"role": "user", "content": "Reply with exactly: pong"}],
        max_tokens=16,
    )
    assert result.content.strip()
    assert result.model == settings.LLM_MODEL
