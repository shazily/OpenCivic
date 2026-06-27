"""Safe LLM invocation through the 5-layer injection defence pipeline."""

from __future__ import annotations

import time
import uuid

from app.core.config import settings
from app.core.errors import AiDisabled, LlmError
from app.services.ai.injection_defence import (
    layer1_sanitise,
    layer2_wrap_context,
    layer3_privilege_check,
    layer4_filter_output,
    layer5_audit,
)
from app.services.ai.llm_provider import LLMResponse, get_llm_provider


async def safe_complete(
    *,
    data_content: str,
    user_question: str,
    user_id: uuid.UUID | None = None,
    dataset_id: uuid.UUID | None = None,
    max_tokens: int = 1000,
) -> LLMResponse:
    """
    Run a data-bound LLM completion through all five defence layers.
    The model has no tool access (layer 3).
    """
    if settings.AI_MODE == "disabled":
        raise AiDisabled(message="AI features are disabled for this deployment.")

    sanitised = layer1_sanitise(data_content, max_length=settings.AI_MAX_CELL_LENGTH)
    if sanitised.injection_flags:
        raise LlmError(
            message="Input blocked by injection defence.",
            code="INJECTION_DETECTED",
        )

    system_prompt, user_message = layer2_wrap_context(sanitised.content, user_question)
    layer3_privilege_check(has_tools=False)

    started = time.perf_counter()
    provider = get_llm_provider()
    response = await provider.complete(
        system_prompt,
        [{"role": "user", "content": user_message}],
        max_tokens=max_tokens,
    )
    latency_ms = int((time.perf_counter() - started) * 1000)

    filtered = layer4_filter_output(response.content)
    layer5_audit(
        user_id=user_id,
        dataset_id=dataset_id,
        input_content=sanitised.content + user_question,
        output_content=filtered.content,
        model=response.model,
        latency_ms=latency_ms,
        confidence=response.confidence,
        injection_flags=sanitised.injection_flags,
        output_flags=filtered.flags,
    )
    if not filtered.passed:
        raise LlmError(message="LLM output blocked by safety filter.", code="OUTPUT_BLOCKED")

    return LLMResponse(
        content=filtered.content,
        model=response.model,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        confidence=response.confidence,
    )
