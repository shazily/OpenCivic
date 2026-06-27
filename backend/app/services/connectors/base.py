"""Connector plugin interface and shared types."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ConnectionTestResult:
    """Result of a connector connectivity check."""

    ok: bool
    message: str


@dataclass(frozen=True)
class SchemaSnapshot:
    """Inferred schema from a connector pull."""

    columns: list[dict[str, Any]]
    row_count: int = 0


@dataclass(frozen=True)
class RecordBatch:
    """Batch of records from a connector pull."""

    rows: list[dict[str, Any]] = field(default_factory=list)
    schema: SchemaSnapshot | None = None


class ConnectorBase(ABC):
    """Abstract connector — all plugins implement this interface."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    @abstractmethod
    async def test_connection(self) -> ConnectionTestResult: ...

    @abstractmethod
    async def get_schema(self) -> SchemaSnapshot: ...

    @abstractmethod
    async def pull(self, since: datetime | None) -> AsyncIterator[RecordBatch]: ...

    @classmethod
    def parse_config(cls, raw: bytes) -> dict[str, Any]:
        from app.core.encryption import decrypt

        return json.loads(decrypt(raw))
