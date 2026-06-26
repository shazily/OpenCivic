"""Ollama LLM provider tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai.llm_provider import OllamaProvider


@pytest.mark.asyncio
async def test_ollama_complete_parses_response() -> None:
    provider = OllamaProvider()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "message": {"content": "Hello from Ollama"},
        "prompt_eval_count": 10,
        "eval_count": 5,
    }
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await provider.complete("system", [{"role": "user", "content": "hi"}])

    assert result.content == "Hello from Ollama"
    assert result.output_tokens == 5
