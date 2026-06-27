"""PostgreSQL connector — asyncpg, read-only enforcement, updated_at watermark."""
import uuid
from datetime import datetime
from typing import Any, AsyncIterator

import asyncpg
import structlog

from connectors.base.connector_base import ConnectorBase, ConnectionTestResult, RecordBatch, SchemaSnapshot

logger = structlog.get_logger(__name__)


class PostgresConnector(ConnectorBase):
    CONNECTOR_TYPE = "postgres"

    async def test_connection(self) -> ConnectionTestResult:
        import time
        try:
            start = time.monotonic()
            conn = await asyncpg.connect(self._config["dsn"], command_timeout=10)
            await conn.fetchval("SELECT 1")
            await conn.close()
            return ConnectionTestResult(success=True, message="OK", latency_ms=int((time.monotonic() - start) * 1000))
        except Exception as e:
            return ConnectionTestResult(success=False, message=str(e))

    async def get_schema(self) -> SchemaSnapshot:
        conn = await asyncpg.connect(self._config["dsn"], command_timeout=30)
        schema, table = self._config.get("schema", "public"), self._config["table"]
        try:
            await conn.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")
            cols = await conn.fetch(
                "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
                "WHERE table_schema=$1 AND table_name=$2 ORDER BY ordinal_position", schema, table
            )
            count = await conn.fetchval(f'SELECT COUNT(*) FROM "{schema}"."{table}"')
            return SchemaSnapshot(
                columns=[{"name": r["column_name"], "type": r["data_type"], "nullable": r["is_nullable"] == "YES", "cardinality": None} for r in cols],
                row_count=count, sampled_at=datetime.utcnow()
            )
        finally:
            await conn.close()

    async def pull(self, since: datetime | None = None) -> AsyncIterator[RecordBatch]:
        conn = await asyncpg.connect(self._config["dsn"], command_timeout=600)
        schema, table = self._config.get("schema", "public"), self._config["table"]
        watermark = self._config.get("watermark_column")
        batch_size = self._config.get("batch_size", 1000)
        try:
            await conn.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")
            where = f'WHERE "{watermark}" > $1' if since and watermark else ""
            params = [since] if since and watermark else []
            records, batch_num = [], 0
            async for row in conn.cursor(f'SELECT * FROM "{schema}"."{table}" {where}', *params):
                records.append(dict(row))
                if len(records) >= batch_size:
                    batch_num += 1
                    yield RecordBatch(records=records, batch_number=batch_num, total_batches=None)
                    records = []
            if records:
                yield RecordBatch(records=records, batch_number=batch_num + 1, total_batches=batch_num + 1)
        finally:
            await conn.close()

    async def close(self) -> None:
        pass
