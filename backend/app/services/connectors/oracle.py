"""Oracle Database connector — read-only pull via python-oracledb thin mode."""

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


def _map_oracle_type(type_name: str) -> str:
    lowered = type_name.lower()
    if any(token in lowered for token in ("int", "decimal", "float", "double", "number")):
        if "int" in lowered:
            return "integer"
        return "number"
    if "bool" in lowered:
        return "boolean"
    if any(token in lowered for token in ("date", "time")):
        return "datetime"
    return "string"


class OracleConnector(ConnectorBase):
    """Pull tabular rows from Oracle Database."""

    def _connect_kwargs(self) -> dict[str, Any]:
        host = self.config.get("host")
        user = self.config.get("user")
        password = self.config.get("password", "")
        service_name = self.config.get("service_name") or self.config.get("database")
        if not all(isinstance(value, str) and value for value in (host, user, service_name)):
            raise ValueError("Connector config requires host, user, and service_name strings.")
        return {
            "host": host,
            "port": int(self.config.get("port", 1521)),
            "user": user,
            "password": str(password),
            "service_name": service_name,
        }

    def _dsn(self) -> str:
        import oracledb

        cfg = self._connect_kwargs()
        return oracledb.makedsn(cfg["host"], cfg["port"], service_name=cfg["service_name"])

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
                return f"SELECT * FROM ({base}) WHERE ROWNUM <= {limit}"
            return base
        table = self._table()
        if limit is not None:
            return f"SELECT * FROM {table} WHERE ROWNUM <= {limit}"
        return f"SELECT * FROM {table}"

    def _schema_from_rows(self, rows: list[dict[str, Any]]) -> SchemaSnapshot:
        if not rows:
            return SchemaSnapshot(columns=[], row_count=0)
        sample = rows[0]
        columns = [
            {
                "name": key,
                "type": _map_oracle_type(type(value).__name__),
                "nullable": value is None,
            }
            for key, value in sample.items()
        ]
        return SchemaSnapshot(columns=columns, row_count=len(rows))

    async def test_connection(self) -> ConnectionTestResult:
        import oracledb

        cfg = self._connect_kwargs()
        try:
            conn = await oracledb.connect_async(
                user=cfg["user"],
                password=cfg["password"],
                dsn=self._dsn(),
            )
            try:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT 1 FROM DUAL")
                    await cursor.fetchone()
            finally:
                await conn.close()
            return ConnectionTestResult(ok=True, message="Connection successful.")
        except Exception as exc:
            return ConnectionTestResult(ok=False, message=str(exc))

    async def get_schema(self) -> SchemaSnapshot:
        import oracledb

        cfg = self._connect_kwargs()
        conn = await oracledb.connect_async(
            user=cfg["user"],
            password=cfg["password"],
            dsn=self._dsn(),
        )
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
        import oracledb

        cfg = self._connect_kwargs()
        conn = await oracledb.connect_async(
            user=cfg["user"],
            password=cfg["password"],
            dsn=self._dsn(),
        )
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
