"""Chat with dataset — schema lock, sandbox SQL, cited answers, confidence gate."""

from __future__ import annotations

import re
import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AiDisabled, DatasetDataNotAvailable, LlmError, ValidationError
from app.repositories.dataset_repository import DatasetRepository
from app.services.ai.injection_defence import layer1_sanitise
from app.services.ai.llm_pipeline import safe_complete
from app.services.data.dataset_data_reader import DatasetDataReader
from app.services.data.duckdb_sandbox import execute_select_on_parquet, validate_select_sql
from app.services.storage.storage_client import get_storage_client

logger = structlog.get_logger(__name__)

LOW_CONFIDENCE_MESSAGE = "I could not find this in the data."
AI_WATERMARK = "AI-assisted. Verify against source data."


def _schema_columns(schema_snapshot: dict | None) -> list[dict[str, str]]:
    columns = (schema_snapshot or {}).get("columns", [])
    return [col for col in columns if isinstance(col, dict) and col.get("name")]


def _schema_summary(columns: list[dict[str, str]], row_count: int | None) -> str:
    lines = [f"row_count: {row_count or 0}"]
    for col in columns[:30]:
        lines.append(f"- {col.get('name')}: {col.get('type', 'string')}")
    return "\n".join(lines)


def _extract_sql(content: str) -> str | None:
    fenced = re.search(r"```(?:sql)?\s*([\s\S]*?)```", content, re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()
    match = re.search(r"(SELECT[\s\S]+)", content, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _heuristic_answer(
    question: str,
    *,
    columns: list[dict[str, str]],
    row_count: int | None,
    parquet_bytes: bytes | None,
) -> dict[str, object]:
    """Rule-based answers when AI is disabled or LLM is unavailable."""
    lowered = question.lower()
    column_names = [str(col["name"]) for col in columns]

    if any(token in lowered for token in ("how many rows", "row count", "number of rows")):
        return {
            "answer": f"This dataset contains {row_count or 0} rows.",
            "confidence": 1.0,
            "ai_assisted": False,
            "citation": {"columns": column_names, "query": None, "rows": []},
        }

    if "column" in lowered or "fields" in lowered or "schema" in lowered:
        return {
            "answer": f"Columns ({len(column_names)}): {', '.join(column_names)}.",
            "confidence": 1.0,
            "ai_assisted": False,
            "citation": {"columns": column_names, "query": None, "rows": []},
        }

    for name in column_names:
        if name.lower() in lowered and parquet_bytes and any(
            word in lowered for word in ("average", "mean", "avg", "sum", "total", "max", "min")
        ):
            agg = "AVG"
            if "sum" in lowered or "total" in lowered:
                agg = "SUM"
            elif "max" in lowered:
                agg = "MAX"
            elif "min" in lowered:
                agg = "MIN"
            sql = f"SELECT {agg}({name}) AS result FROM data"
            try:
                validate_select_sql(sql)
                rows = execute_select_on_parquet(parquet_bytes, sql, max_rows=1)
                value = rows[0].get("result") if rows else None
                return {
                    "answer": f"{agg} of {name}: {value}",
                    "confidence": 0.9,
                    "ai_assisted": False,
                    "citation": {"columns": [name], "query": sql, "rows": rows[:5]},
                }
            except ValidationError:
                break

    return {
        "answer": (
            "AI chat is disabled in this deployment. "
            f"Dataset has {row_count or 0} rows and columns: {', '.join(column_names[:10])}."
        ),
        "confidence": 0.6,
        "ai_assisted": False,
        "citation": {"columns": column_names, "query": None, "rows": []},
    }


async def chat_with_dataset(
    session: AsyncSession,
    dataset_id: uuid.UUID,
    question: str,
    *,
    user_id: uuid.UUID | None = None,
) -> dict[str, object]:
    """Answer a natural-language question about a published dataset."""
    sanitised = layer1_sanitise(question, max_length=500)
    if sanitised.injection_flags:
        raise LlmError(message="Question blocked by injection defence.", code="INJECTION_DETECTED")

    repo = DatasetRepository(session)
    dataset = await repo.get_by_id(dataset_id)
    if dataset.status != "published":
        raise DatasetDataNotAvailable(message="Chat is only available for published datasets.")

    columns = _schema_columns(dataset.schema_snapshot)
    if not columns:
        raise DatasetDataNotAvailable(message="Dataset schema is not available.")

    reader = DatasetDataReader(session, get_storage_client())
    try:
        _, _, _, _, version_number = await reader.read_page(dataset_id, page_size=1, cursor=None, fields=None, sort=None)
    except DatasetDataNotAvailable:
        raise

    from sqlalchemy import select

    from app.db.models import DatasetVersion

    version = await session.scalar(
        select(DatasetVersion)
        .where(DatasetVersion.dataset_id == dataset_id, DatasetVersion.storage_path.is_not(None))
        .order_by(DatasetVersion.version_number.desc())
        .limit(1)
    )
    if version is None or not version.storage_path:
        raise DatasetDataNotAvailable(message="No ingested data available.")

    storage = get_storage_client()
    parquet_bytes = await storage.get(version.storage_path)
    schema_text = _schema_summary(columns, dataset.row_count)

    if settings.AI_MODE == "disabled":
        result = _heuristic_answer(
            sanitised.content,
            columns=columns,
            row_count=dataset.row_count,
            parquet_bytes=parquet_bytes,
        )
        result["watermark"] = None
        result["dataset_id"] = str(dataset_id)
        result["version_number"] = version_number
        return result

    sql: str | None = None
    rows: list[dict[str, object]] = []
    confidence = 0.0

    try:
        sql_prompt = (
            "Generate a DuckDB SQL SELECT query against table `data` only. "
            "Use exact column names from the schema. Return SQL only, no explanation."
        )
        sql_response = await safe_complete(
            data_content=schema_text,
            user_question=f"{sql_prompt}\n\nUser question: {sanitised.content}",
            user_id=user_id,
            dataset_id=dataset_id,
            max_tokens=400,
        )
        extracted = _extract_sql(sql_response.content)
        if extracted:
            sql = validate_select_sql(extracted)
            rows = execute_select_on_parquet(parquet_bytes, sql)
            confidence = sql_response.confidence
    except (AiDisabled, LlmError, ValidationError) as exc:
        logger.info("chat_sql_fallback", dataset_id=str(dataset_id), reason=str(exc))
        return _heuristic_answer(
            sanitised.content,
            columns=columns,
            row_count=dataset.row_count,
            parquet_bytes=parquet_bytes,
        ) | {
            "dataset_id": str(dataset_id),
            "version_number": version_number,
            "watermark": None,
        }

    if confidence < settings.LLM_CONFIDENCE_THRESHOLD or not rows:
        return {
            "answer": LOW_CONFIDENCE_MESSAGE,
            "confidence": confidence,
            "ai_assisted": True,
            "watermark": AI_WATERMARK,
            "dataset_id": str(dataset_id),
            "version_number": version_number,
            "citation": {"columns": [c["name"] for c in columns], "query": sql, "rows": rows[:5]},
        }

    result_preview = json_preview(rows[:10])
    narrate_prompt = (
        "Narrate the query results to answer the user's question. "
        "Only use values from the results. Cite the SQL query used."
    )
    narration = await safe_complete(
        data_content=result_preview,
        user_question=f"{narrate_prompt}\n\nQuestion: {sanitised.content}\nSQL: {sql}",
        user_id=user_id,
        dataset_id=dataset_id,
        max_tokens=600,
    )
    if narration.confidence < settings.LLM_CONFIDENCE_THRESHOLD:
        return {
            "answer": LOW_CONFIDENCE_MESSAGE,
            "confidence": narration.confidence,
            "ai_assisted": True,
            "watermark": AI_WATERMARK,
            "dataset_id": str(dataset_id),
            "version_number": version_number,
            "citation": {"columns": [c["name"] for c in columns], "query": sql, "rows": rows[:5]},
        }

    return {
        "answer": narration.content,
        "confidence": narration.confidence,
        "ai_assisted": True,
        "watermark": AI_WATERMARK,
        "dataset_id": str(dataset_id),
        "version_number": version_number,
        "citation": {"columns": [c["name"] for c in columns], "query": sql, "rows": rows[:5]},
    }


def json_preview(rows: list[dict[str, object]]) -> str:
    import json

    return json.dumps(rows, default=str)[:4000]
