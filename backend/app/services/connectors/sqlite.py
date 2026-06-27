"""SQLite connector — read-only pull from a local database file."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from app.services.connectors.base import (
    ConnectionTestResult,
    ConnectorBase,
    RecordBatch,
    SchemaSnapshot,
)


def _map_sqlite_type(type_name: str) -> str:
    lowered = type_name.lower()
    if "int" in lowered:
        return "integer"
    if any(token in lowered for token in ("real", "float", "double", "numeric")):
        return "number"
    if "bool" in lowered:
        return "boolean"
    return "string"


class SqliteConnector(ConnectorBase):
    """Pull rows from a SQLite database file via aiosqlite."""

    def _database_path(self) -> str:
        path = self.config.get("path") or self.config.get("database")
        if not isinstance(path, str) or not path:
            raise ValueError("Connector config requires a path or database string.")
        return path

    def _table(self) -> str:
        table = self.config.get("table")
        if not isinstance(table, str) or not table:
            raise ValueError("Connector config requires a table string.")
        return table

    def _select_sql(self, *, limit: int | None = None) -> str:
        query = self.config.get("query")
        if isinstance(query, str) and query.strip():
            base = query.strip().rstrip(";")
            if limit is not None:
                return f"SELECT * FROM ({base}) LIMIT {limit}"
            return base
        table = self._table()
        if limit is not None:
            return f'SELECT * FROM "{table}" LIMIT {limit}'
        return f'SELECT * FROM "{table}"'

    def _schema_from_rows(self, rows: list[dict[str, Any]]) -> SchemaSnapshot:
        if not rows:
            return SchemaSnapshot(columns=[], row_count=0)
        sample = rows[0]
        columns = [
            {
                "name": key,
                "type": _map_sqlite_type(type(value).__name__),
                "nullable": value is None,
            }
            for key, value in sample.items()
        ]
        return SchemaSnapshot(columns=columns, row_count=len(rows))

    async def test_connection(self) -> ConnectionTestResult:
        import aiosqlite

        try:
            async with aiosqlite.connect(self._database_path()) as conn:
                async with conn.execute("SELECT 1") as cursor:
                    await cursor.fetchone()
            return ConnectionTestResult(ok=True, message="Connection successful.")
        except Exception as exc:
            return ConnectionTestResult(ok=False, message=str(exc))

    async def get_schema(self) -> SchemaSnapshot:
        import aiosqlite

        async with aiosqlite.connect(self._database_path()) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(self._select_sql(limit=100)) as cursor:
                rows = [dict(row) for row in await cursor.fetchall()]
        return self._schema_from_rows(rows)

    async def pull(self, since: datetime | None) -> AsyncIterator[RecordBatch]:
        del since
        import aiosqlite

        async with aiosqlite.connect(self._database_path()) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(self._select_sql()) as cursor:
                rows = [dict(row) for row in await cursor.fetchall()]
        schema = self._schema_from_rows(rows)
        yield RecordBatch(rows=rows, schema=schema)
