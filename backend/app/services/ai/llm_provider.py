"""
OpenCivic — LLM Provider abstraction.
RULE: ALL LLM calls go through this interface — never call OpenAI/Anthropic SDK directly.
Switch providers via LLM_PROVIDER env var. Zero application code changes.
Air-gapped deployments use Ollama only — no data leaves the perimeter.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import structlog

from app.core.config import settings
from app.core.errors import AiDisabled

logger = structlog.get_logger(__name__)


@dataclass
class LLMResponse:
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    confidence: float = 1.0  # 0–1, used by hallucination prevention gate


class LLMProvider(ABC):
    """Abstract LLM provider. One implementation per backend."""

    @abstractmethod
    async def complete(
        self, system: str, messages: list[dict[str, str]], max_tokens: int = 1000
    ) -> LLMResponse:
        """Generate a completion. messages = [{role, content}]"""

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Generate a vector embedding for semantic search."""


class OpenAIProvider(LLMProvider):
    async def complete(
        self, system: str, messages: list[dict[str, str]], max_tokens: int = 1000
    ) -> LLMResponse:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.LLM_API_KEY)
        resp = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[{"role": "system", "content": system}, *messages],
            max_tokens=max_tokens,
            temperature=settings.LLM_TEMPERATURE,
        )
        return LLMResponse(
            content=resp.choices[0].message.content or "",
            model=resp.model,
            input_tokens=resp.usage.prompt_tokens,
            output_tokens=resp.usage.completion_tokens,
        )

    async def embed(self, text: str) -> list[float]:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.LLM_API_KEY)
        resp = await client.embeddings.create(model="text-embedding-3-small", input=text)
        return resp.data[0].embedding


class AnthropicProvider(LLMProvider):
    async def complete(
        self, system: str, messages: list[dict[str, str]], max_tokens: int = 1000
    ) -> LLMResponse:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=settings.LLM_API_KEY)
        resp = await client.messages.create(
            model=settings.LLM_MODEL,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
        )
        return LLMResponse(
            content=resp.content[0].text,
            model=resp.model,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
        )

    async def embed(self, text: str) -> list[float]:
        # Use sentence-transformers for embeddings when using Anthropic
        return await _local_embed(text)


class OllamaProvider(LLMProvider):
    """Local Ollama — required for air-gapped deployments."""

    async def complete(
        self, system: str, messages: list[dict[str, str]], max_tokens: int = 1000
    ) -> LLMResponse:
        import httpx

        url = f"{settings.LLM_BASE_URL}/api/chat"
        payload = {
            "model": settings.LLM_MODEL,
            "messages": [{"role": "system", "content": system}, *messages],
            "stream": False,
            "options": {"temperature": settings.LLM_TEMPERATURE, "num_predict": max_tokens},
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        return LLMResponse(
            content=data["message"]["content"],
            model=settings.LLM_MODEL,
            input_tokens=data.get("prompt_eval_count", 0),
            output_tokens=data.get("eval_count", 0),
        )

    async def embed(self, text: str) -> list[float]:
        import httpx

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{settings.LLM_BASE_URL}/api/embeddings",
                json={"model": "nomic-embed-text", "prompt": text},
            )
            resp.raise_for_status()
            return resp.json()["embedding"]


async def _local_embed(text: str) -> list[float]:
    """Local embeddings — sentence-transformers when installed, else deterministic hash vectors."""
    import asyncio
    import hashlib

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        vector: list[float] = []
        index = 0
        while len(vector) < 384:
            vector.append((digest[index % len(digest)] / 127.5) - 1.0)
            index += 1
        return vector

    loop = asyncio.get_event_loop()
    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    embedding = await loop.run_in_executor(None, model.encode, text)
    return embedding.tolist()


def get_llm_provider() -> LLMProvider:
    """
    Factory — returns the configured LLM provider.
    Raises AiDisabled if AI_MODE=disabled.
    RULE: air-gapped deployments only get OllamaProvider.
    """
    if settings.AI_MODE == "disabled":
        raise AiDisabled(message="AI features are disabled for this deployment.")
    if settings.DEPLOYMENT_MODE == "airgap" and settings.LLM_PROVIDER != "ollama":
        raise AiDisabled(message="Air-gapped deployments must use Ollama.")
    providers = {
        "openai": OpenAIProvider,
        "openai_compatible": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "ollama": OllamaProvider,
    }
    cls = providers.get(settings.LLM_PROVIDER, OllamaProvider)
    return cls()
