"""AI-assisted DCAT-3 metadata suggestions with heuristic fallback."""

from __future__ import annotations

import json
import re
import uuid

from app.core.config import settings
from app.core.errors import AiDisabled
from app.db.models import Dataset
from app.services.ai.llm_pipeline import safe_complete


def _heuristic_suggestions(dataset: Dataset) -> dict[str, object]:
    """Rule-based metadata when AI is disabled or unavailable."""
    columns = (dataset.schema_snapshot or {}).get("columns", [])
    column_names = [col.get("name", "") for col in columns if col.get("name")]
    theme = dataset.tags[0] if dataset.tags else "government"
    description = dataset.description or (
        f"{dataset.title} — open dataset with {len(column_names)} fields"
        + (f" ({', '.join(column_names[:5])})" if column_names else "")
    )
    return {
        "title": dataset.title,
        "description": description[:2000],
        "tags": dataset.tags or ["open-data"],
        "metadata": {
            "dct:publisher": "OpenCivic Publisher",
            "dcat:theme": theme,
            "dct:language": "en",
            "dct:license": "https://creativecommons.org/licenses/by/4.0/",
        },
        "ai_assisted": False,
        "confidence": 0.5,
    }


async def suggest_dataset_metadata(
    dataset: Dataset,
    *,
    user_id: uuid.UUID | None = None,
) -> dict[str, object]:
    """
    Suggest DCAT-3 metadata for a dataset.
    Uses LLM in assist/automate mode; falls back to heuristics when AI is disabled.
    """
    if settings.AI_MODE == "disabled":
        return _heuristic_suggestions(dataset)

    columns = (dataset.schema_snapshot or {}).get("columns", [])
    column_summary = ", ".join(
        f"{col.get('name')}:{col.get('type', 'string')}" for col in columns[:20]
    )
    data_context = (
        f"Title: {dataset.title}\n"
        f"Slug: {dataset.slug}\n"
        f"Row count: {dataset.row_count}\n"
        f"Columns: {column_summary}\n"
        f"Existing tags: {', '.join(dataset.tags)}"
    )
    prompt = (
        "Suggest DCAT-3 metadata as JSON with keys: description, tags (array), "
        "metadata (object with dct:publisher, dcat:theme, dct:language, dct:license). "
        "Return JSON only."
    )

    try:
        response = await safe_complete(
            data_content=data_context,
            user_question=prompt,
            user_id=user_id,
            dataset_id=dataset.id,
            max_tokens=800,
        )
        parsed = _parse_json_object(response.content)
        if parsed:
            return {
                "title": dataset.title,
                "description": parsed.get("description", dataset.description),
                "tags": parsed.get("tags", dataset.tags),
                "metadata": parsed.get("metadata", {}),
                "ai_assisted": True,
                "confidence": response.confidence,
            }
    except (AiDisabled, Exception):
        pass

    return _heuristic_suggestions(dataset)


def _parse_json_object(content: str) -> dict[str, object] | None:
    match = re.search(r"\{[\s\S]*\}", content)
    if not match:
        return None
    try:
        value = json.loads(match.group())
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None
