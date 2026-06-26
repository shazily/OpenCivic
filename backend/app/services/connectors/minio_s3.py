"""S3 / Minio connector — pulls objects by prefix from S3-compatible storage."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from app.services.connectors.base import (
    ConnectionTestResult,
    ConnectorBase,
    RecordBatch,
    SchemaSnapshot,
)


class MinioS3Connector(ConnectorBase):
    """Pull tabular files (CSV or JSON) from an S3-compatible bucket prefix."""

    def _client(self):
        import asyncio

        import boto3
        from botocore.client import Config

        endpoint = self.config.get("endpoint_url") or self.config.get("endpoint")
        access_key = self.config.get("access_key", "")
        secret_key = self.config.get("secret_key", "")
        return boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4"),
        )

    def _bucket(self) -> str:
        bucket = self.config.get("bucket")
        if not isinstance(bucket, str) or not bucket:
            raise ValueError("Connector config requires bucket.")
        return bucket

    def _prefix(self) -> str:
        prefix = self.config.get("prefix", "")
        return str(prefix) if prefix else ""

    async def _list_keys(self) -> list[str]:
        import asyncio

        bucket = self._bucket()
        prefix = self._prefix()
        extensions = {".csv", ".json", ".jsonl"}
        client = self._client()

        def _list() -> list[str]:
            keys: list[str] = []
            paginator = client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for item in page.get("Contents", []):
                    key = item.get("Key", "")
                    if any(str(key).lower().endswith(ext) for ext in extensions):
                        keys.append(str(key))
            return sorted(keys)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _list)

    async def _get_object(self, key: str) -> bytes:
        import asyncio

        bucket = self._bucket()
        client = self._client()

        def _get() -> bytes:
            response = client.get_object(Bucket=bucket, Key=key)
            return response["Body"].read()

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get)

    def _parse_rows(self, key: str, payload: bytes) -> list[dict[str, Any]]:
        lowered = key.lower()
        if lowered.endswith(".csv"):
            text = payload.decode("utf-8", errors="replace")
            reader = csv.DictReader(io.StringIO(text))
            return [dict(row) for row in reader]
        if lowered.endswith(".jsonl"):
            rows: list[dict[str, Any]] = []
            for line in payload.decode("utf-8", errors="replace").splitlines():
                if line.strip():
                    item = json.loads(line)
                    if isinstance(item, dict):
                        rows.append(item)
            return rows
        data = json.loads(payload)
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
        if isinstance(data, dict):
            nested = data.get(self.config.get("data_path", "data"), data)
            if isinstance(nested, list):
                return [row for row in nested if isinstance(row, dict)]
        return []

    def _infer_schema(self, rows: list[dict[str, Any]]) -> SchemaSnapshot:
        if not rows:
            return SchemaSnapshot(columns=[], row_count=0)
        columns = [{"name": key, "type": "string", "nullable": True} for key in rows[0]]
        return SchemaSnapshot(columns=columns, row_count=len(rows))

    async def test_connection(self) -> ConnectionTestResult:
        try:
            keys = await self._list_keys()
            if not keys:
                return ConnectionTestResult(ok=True, message="Connected — no tabular objects found.")
            return ConnectionTestResult(ok=True, message=f"Connected — {len(keys)} object(s) found.")
        except Exception as exc:
            return ConnectionTestResult(ok=False, message=str(exc))

    async def get_schema(self) -> SchemaSnapshot:
        keys = await self._list_keys()
        if not keys:
            return SchemaSnapshot(columns=[], row_count=0)
        payload = await self._get_object(keys[0])
        rows = self._parse_rows(keys[0], payload)
        return self._infer_schema(rows)

    async def pull(self, since: datetime | None) -> AsyncIterator[RecordBatch]:
        del since
        keys = await self._list_keys()
        if not keys:
            yield RecordBatch(rows=[], schema=SchemaSnapshot(columns=[], row_count=0))
            return
        payload = await self._get_object(keys[0])
        rows = self._parse_rows(keys[0], payload)
        schema = self._infer_schema(rows)
        yield RecordBatch(rows=rows, schema=schema)
