"""Microsoft SQL Server connector — read-only pull via aioodbc."""

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


def _map_mssql_type(type_name: str) -> str:
    lowered = type_name.lower()
    if "int" in lowered or lowered in {"bigint", "smallint", "tinyint"}:
        return "integer"
    if any(token in lowered for token in ("decimal", "float", "real", "numeric", "money")):
        return "number"
    if "bool" in lowered or lowered == "bit":
        return "boolean"
    if any(token in lowered for token in ("date", "time")):
        return "datetime"
    return "string"


class MssqlConnector(ConnectorBase):
    """Pull tabular rows from Microsoft SQL Server."""

    def _connect_kwargs(self) -> dict[str, Any]:
        host = self.config.get("host")
        database = self.config.get("database")
        user = self.config.get("user")
        password = self.config.get("password", "")
        if not all(isinstance(value, str) and value for value in (host, database, user)):
            raise ValueError("Connector config requires host, database, and user strings.")
        port = int(self.config.get("port", 1433))
        driver = self.config.get("driver", "ODBC Driver 18 for SQL Server")
        return {
            "host": host,
            "port": port,
            "database": database,
            "user": user,
            "password": str(password),
            "driver": driver,
        }

    def _dsn(self) -> str:
        cfg = self._connect_kwargs()
        return (
            f"DRIVER={{{cfg['driver']}}};"
            f"SERVER={cfg['host']},{cfg['port']};"
            f"DATABASE={cfg['database']};"
            f"UID={cfg['user']};"
            f"PWD={cfg['password']};"
            "TrustServerCertificate=yes;"
        )

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
                return f"SELECT TOP ({limit}) * FROM ({base}) AS subq"
            return base
        table = self._table()
        if limit is not None:
            return f"SELECT TOP ({limit}) * FROM [{table}]"
        return f"SELECT * FROM [{table}]"

    def _schema_from_rows(self, rows: list[dict[str, Any]]) -> SchemaSnapshot:
        if not rows:
            return SchemaSnapshot(columns=[], row_count=0)
        sample = rows[0]
        columns = [
            {
                "name": key,
                "type": _map_mssql_type(type(value).__name__),
                "nullable": value is None,
            }
            for key, value in sample.items()
        ]
        return SchemaSnapshot(columns=columns, row_count=len(rows))

    async def test_connection(self) -> ConnectionTestResult:
        import aioodbc

        try:
            conn = await aioodbc.connect(dsn=self._dsn())
            try:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT 1")
                    await cursor.fetchone()
            finally:
                await conn.close()
            return ConnectionTestResult(ok=True, message="Connection successful.")
        except Exception as exc:
            return ConnectionTestResult(ok=False, message=str(exc))

    async def get_schema(self) -> SchemaSnapshot:
        import aioodbc

        conn = await aioodbc.connect(dsn=self._dsn())
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(self._select_sql(limit=100))
                columns = [column[0] for column in cursor.description or []]
                raw_rows = await cursor.fetchall()
                rows = [dict(zip(columns, row, strict=False)) for row in raw_rows]
            return self._schema_from_rows(rows)
        finally:
            await conn.close()

    async def pull(self, since: datetime | None) -> AsyncIterator[RecordBatch]:
        del since
        import aioodbc

        conn = await aioodbc.connect(dsn=self._dsn())
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(self._select_sql())
                columns = [column[0] for column in cursor.description or []]
                raw_rows = await cursor.fetchall()
                rows = [dict(zip(columns, row, strict=False)) for row in raw_rows]
            schema = self._schema_from_rows(rows)
            yield RecordBatch(rows=rows, schema=schema)
        finally:
            await conn.close()
