"""PostgreSQL connector — pulls rows from a configured table or SQL query."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

import asyncpg

from app.services.connectors.base import (
    ConnectionTestResult,
    ConnectorBase,
    RecordBatch,
    SchemaSnapshot,
)


def _map_pg_type(type_name: str) -> str:
    lowered = type_name.lower()
    if any(token in lowered for token in ("int", "serial")):
        return "integer"
    if any(token in lowered for token in ("float", "double", "numeric", "decimal", "real")):
        return "number"
    if "bool" in lowered:
        return "boolean"
    if any(token in lowered for token in ("timestamp", "date", "time")):
        return "datetime"
    return "string"


class PostgresConnector(ConnectorBase):
    """Read-only pull from PostgreSQL via asyncpg."""

    def _dsn_kwargs(self) -> dict[str, Any]:
        host = self.config.get("host")
        database = self.config.get("database")
        user = self.config.get("user")
        password = self.config.get("password", "")
        if not all(isinstance(value, str) and value for value in (host, database, user)):
            raise ValueError("Connector config requires host, database, and user strings.")
        return {
            "host": host,
            "port": int(self.config.get("port", 5432)),
            "database": database,
            "user": user,
            "password": str(password),
        }

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
                return f"SELECT * FROM ({base}) AS subq LIMIT {limit}"
            return base
        table = self._table()
        if limit is not None:
            return f'SELECT * FROM "{table}" LIMIT {limit}'
        return f'SELECT * FROM "{table}"'

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(**self._dsn_kwargs())

    def _rows_to_dicts(self, records: list[asyncpg.Record]) -> list[dict[str, Any]]:
        return [dict(record) for record in records]

    def _schema_from_records(
        self, records: list[asyncpg.Record], *, row_count: int
    ) -> SchemaSnapshot:
        if not records:
            return SchemaSnapshot(columns=[], row_count=0)
        sample = records[0]
        columns = [
            {
                "name": key,
                "type": _map_pg_type(type(value).__name__),
                "nullable": value is None,
            }
            for key, value in dict(sample).items()
        ]
        return SchemaSnapshot(columns=columns, row_count=row_count)

    async def test_connection(self) -> ConnectionTestResult:
        try:
            conn = await self._connect()
            try:
                await conn.fetchval("SELECT 1")
            finally:
                await conn.close()
            return ConnectionTestResult(ok=True, message="Connection successful.")
        except Exception as exc:
            return ConnectionTestResult(ok=False, message=str(exc))

    async def get_schema(self) -> SchemaSnapshot:
        conn = await self._connect()
        try:
            records = await conn.fetch(self._select_sql(limit=100))
            return self._schema_from_records(records, row_count=len(records))
        finally:
            await conn.close()

    async def pull(self, since: datetime | None) -> AsyncIterator[RecordBatch]:
        del since
        conn = await self._connect()
        try:
            records = await conn.fetch(self._select_sql())
            rows = self._rows_to_dicts(records)
            schema = self._schema_from_records(records, row_count=len(rows))
            yield RecordBatch(rows=rows, schema=schema)
        finally:
            await conn.close()
