"""REST API connector — fetches JSON or CSV from a URL."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

import httpx

from app.services.connectors.base import (
    ConnectionTestResult,
    ConnectorBase,
    RecordBatch,
    SchemaSnapshot,
)


class RestApiConnector(ConnectorBase):
    """Pull tabular data from a REST endpoint."""

    async def _fetch_bytes(self) -> bytes:
        url = self.config.get("url")
        if not isinstance(url, str) or not url:
            raise ValueError("Connector config requires a url string.")
        headers: dict[str, str] = {}
        auth_type = self.config.get("auth_type", "none")
        if auth_type == "bearer":
            token = self.config.get("token", "")
            headers["Authorization"] = f"Bearer {token}"
        elif auth_type == "api_key":
            header_name = self.config.get("api_key_header", "X-API-Key")
            headers[header_name] = str(self.config.get("api_key", ""))
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.content

    def _parse_rows(self, payload: bytes) -> list[dict[str, Any]]:
        content_type = str(self.config.get("content_type", "json")).lower()
        if content_type == "csv":
            text = payload.decode("utf-8", errors="replace")
            reader = csv.DictReader(io.StringIO(text))
            return [dict(row) for row in reader]
        data = json.loads(payload)
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
        if isinstance(data, dict):
            path = self.config.get("data_path", "data")
            nested = data.get(path, data)
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
            await self._fetch_bytes()
            return ConnectionTestResult(ok=True, message="Connection successful.")
        except Exception as exc:
            return ConnectionTestResult(ok=False, message=str(exc))

    async def get_schema(self) -> SchemaSnapshot:
        payload = await self._fetch_bytes()
        rows = self._parse_rows(payload)
        return self._infer_schema(rows)

    async def pull(self, since: datetime | None) -> AsyncIterator[RecordBatch]:
        del since
        payload = await self._fetch_bytes()
        rows = self._parse_rows(payload)
        schema = self._infer_schema(rows)
        yield RecordBatch(rows=rows, schema=schema)
