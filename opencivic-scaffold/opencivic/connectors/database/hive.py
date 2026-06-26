"""Hive/Cloudera connector — PyHive, Kerberos, Knox gateway, partition-aware incremental."""
import asyncio
import uuid
from datetime import datetime
from typing import Any, AsyncIterator

import structlog

from connectors.base.connector_base import ConnectorBase, ConnectionTestResult, RecordBatch, SchemaSnapshot

logger = structlog.get_logger(__name__)


class HiveConnector(ConnectorBase):
    """
    HiveServer2 connector. Auth: KERBEROS | LDAP | NONE.
    For Kerberos: valid keytab and KDC config required on worker host.
    Runs PyHive (sync) in thread pool executor — never blocks the event loop.
    """
    CONNECTOR_TYPE = "hive"

    def _sync_connect(self):
        from pyhive import hive
        auth = self._config.get("auth", "NONE")
        host, port = self._config["host"], self._config.get("port", 10000)
        database = self._config.get("database", "default")
        if auth == "KERBEROS":
            return hive.connect(host=host, port=port, database=database, auth="KERBEROS", kerberos_service_name="hive")
        elif auth == "LDAP":
            return hive.connect(host=host, port=port, database=database, auth="LDAP",
                                username=self._config["username"], password=self._config["password"])
        return hive.connect(host=host, port=port, database=database)

    async def test_connection(self) -> ConnectionTestResult:
        import time
        try:
            start = time.monotonic()
            loop = asyncio.get_event_loop()
            conn = await loop.run_in_executor(None, self._sync_connect)
            cur = conn.cursor()
            await loop.run_in_executor(None, cur.execute, "SELECT 1")
            conn.close()
            return ConnectionTestResult(success=True, message="OK", latency_ms=int((time.monotonic() - start) * 1000))
        except Exception as e:
            return ConnectionTestResult(success=False, message=str(e))

    async def get_schema(self) -> SchemaSnapshot:
        loop = asyncio.get_event_loop()
        db, table = self._config.get("database", "default"), self._config["table"]
        def fetch():
            conn = self._sync_connect()
            cur = conn.cursor()
            cur.execute(f"DESCRIBE `{db}`.`{table}`")
            cols = cur.fetchall()
            cur.execute(f"SELECT COUNT(*) FROM `{db}`.`{table}`")
            count = cur.fetchone()[0]
            conn.close()
            return cols, count
        cols, count = await loop.run_in_executor(None, fetch)
        return SchemaSnapshot(
            columns=[{"name": r[0], "type": r[1], "nullable": True, "cardinality": None} for r in cols],
            row_count=count, sampled_at=datetime.utcnow()
        )

    async def pull(self, since: datetime | None = None) -> AsyncIterator[RecordBatch]:
        loop = asyncio.get_event_loop()
        db, table = self._config.get("database", "default"), self._config["table"]
        partition_col = self._config.get("partition_column")
        batch_size = self._config.get("batch_size", 5000)
        where = f"WHERE `{partition_col}` > '{since.strftime('%Y-%m-%d %H:%M:%S')}'" if since and partition_col else ""
        offset, batch_num = 0, 0
        while True:
            def fetch_batch(off=offset):
                conn = self._sync_connect()
                cur = conn.cursor()
                cur.execute(f"SELECT * FROM `{db}`.`{table}` {where} LIMIT {batch_size} OFFSET {off}")
                rows = cur.fetchall()
                names = [d[0] for d in cur.description] if rows else []
                conn.close()
                return [dict(zip(names, r)) for r in rows]
            records = await loop.run_in_executor(None, fetch_batch)
            if not records:
                break
            batch_num += 1
            yield RecordBatch(records=records, batch_number=batch_num, total_batches=None)
            offset += batch_size

    async def close(self) -> None:
        pass
