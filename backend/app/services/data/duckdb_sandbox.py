"""Validated DuckDB SELECT execution against Parquet in an isolated subprocess."""

from __future__ import annotations

import json
import multiprocessing
import re
import tempfile
import uuid
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.errors import ValidationError

_FORBIDDEN_SQL = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|COPY|EXECUTE|GRANT|REVOKE|"
    r"TRUNCATE|MERGE|CALL|PRAGMA|LOAD|EXPORT|IMPORT)\b",
    re.IGNORECASE,
)


def validate_select_sql(sql: str) -> str:
    """Ensure SQL is a single read-only SELECT against the sandbox view."""
    cleaned = sql.strip().rstrip(";").strip()
    if not cleaned:
        raise ValidationError(message="Empty SQL query.", field="query")
    if ";" in cleaned:
        raise ValidationError(message="Multiple SQL statements are not allowed.", field="query")
    if "--" in cleaned or "/*" in cleaned:
        raise ValidationError(message="SQL comments are not allowed.", field="query")
    if not cleaned.upper().startswith("SELECT"):
        raise ValidationError(message="Only SELECT queries are allowed.", field="query")
    if _FORBIDDEN_SQL.search(cleaned):
        raise ValidationError(message="Forbidden SQL keyword detected.", field="query")
    return cleaned


def _worker(parquet_path: str, sql: str, result_path: str) -> None:
    import duckdb

    connection = duckdb.connect()
    try:
        connection.execute(
            f"CREATE VIEW data AS SELECT * FROM read_parquet('{parquet_path.replace(chr(39), chr(39)*2)}')"
        )
        frame = connection.execute(sql).fetchdf()
        rows = json.loads(frame.to_json(orient="records"))
    finally:
        connection.close()

    Path(result_path).write_text(json.dumps(rows), encoding="utf-8")


def execute_select_on_parquet(
    parquet_bytes: bytes,
    sql: str,
    *,
    timeout_seconds: int | None = None,
    max_rows: int = 100,
) -> list[dict[str, Any]]:
    """Run a validated SELECT in a subprocess with a hard timeout."""
    validated = validate_select_sql(sql)
    limited_sql = validated
    if "LIMIT" not in validated.upper():
        limited_sql = f"{validated} LIMIT {max_rows}"

    timeout = timeout_seconds or settings.AI_SANDBOX_TIMEOUT_SECONDS
    with tempfile.TemporaryDirectory() as tmp:
        parquet_path = str(Path(tmp) / f"{uuid.uuid4().hex}.parquet")
        result_path = str(Path(tmp) / "result.json")
        Path(parquet_path).write_bytes(parquet_bytes)

        process = multiprocessing.Process(
            target=_worker,
            args=(parquet_path, limited_sql, result_path),
        )
        process.start()
        process.join(timeout)
        if process.is_alive():
            process.terminate()
            process.join()
            raise ValidationError(message="Query timed out.", field="query")
        if process.exitcode != 0:
            raise ValidationError(message="Query execution failed.", field="query")
        if not Path(result_path).exists():
            raise ValidationError(message="Query returned no result.", field="query")
        payload = json.loads(Path(result_path).read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValidationError(message="Invalid query result.", field="query")
        return payload
