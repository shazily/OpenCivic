"""MySQL / MariaDB connector — read-only pull via aiomysql."""

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


def _map_mysql_type(type_name: str) -> str:
    lowered = type_name.lower()
    if any(token in lowered for token in ("int", "decimal", "float", "double", "numeric")):
        if "int" in lowered:
            return "integer"
        return "number"
    if "bool" in lowered or lowered == "bit":
        return "boolean"
    if any(token in lowered for token in ("date", "time", "year")):
        return "datetime"
    return "string"


class MysqlConnector(ConnectorBase):
    """Pull tabular rows from MySQL or MariaDB."""

    def _connect_kwargs(self) -> dict[str, Any]:
        host = self.config.get("host")
        database = self.config.get("database")
        user = self.config.get("user")
        password = self.config.get("password", "")
        if not all(isinstance(value, str) and value for value in (host, database, user)):
            raise ValueError("Connector config requires host, database, and user strings.")
        return {
            "host": host,
            "port": int(self.config.get("port", 3306)),
            "db": database,
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
            return f"SELECT * FROM `{table}` LIMIT {limit}"
        return f"SELECT * FROM `{table}`"

    def _schema_from_rows(self, rows: list[dict[str, Any]]) -> SchemaSnapshot:
        if not rows:
            return SchemaSnapshot(columns=[], row_count=0)
        sample = rows[0]
        columns = [
            {
                "name": key,
                "type": _map_mysql_type(type(value).__name__),
                "nullable": value is None,
            }
            for key, value in sample.items()
        ]
        return SchemaSnapshot(columns=columns, row_count=len(rows))

    async def test_connection(self) -> ConnectionTestResult:
        import aiomysql

        try:
            conn = await aiomysql.connect(**self._connect_kwargs())
            try:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT 1")
                    await cursor.fetchone()
            finally:
                conn.close()
            return ConnectionTestResult(ok=True, message="Connection successful.")
        except Exception as exc:
            return ConnectionTestResult(ok=False, message=str(exc))

    async def get_schema(self) -> SchemaSnapshot:
        import aiomysql

        conn = await aiomysql.connect(**self._connect_kwargs())
        try:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(self._select_sql(limit=100))
                rows = await cursor.fetchall()
            return self._schema_from_rows(list(rows))
        finally:
            conn.close()

    async def pull(self, since: datetime | None) -> AsyncIterator[RecordBatch]:
        del since
        import aiomysql

        conn = await aiomysql.connect(**self._connect_kwargs())
        try:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(self._select_sql())
                rows = list(await cursor.fetchall())
            schema = self._schema_from_rows(rows)
            yield RecordBatch(rows=rows, schema=schema)
        finally:
            conn.close()
