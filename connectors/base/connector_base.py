"""
OpenCivic — ConnectorBase abstract class.
Every connector implements this interface. Drop in /connectors, detected on restart.
"""
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, AsyncIterator


@dataclass
class ConnectionTestResult:
    success: bool
    message: str
    latency_ms: int | None = None


@dataclass
class SchemaSnapshot:
    columns: list[dict]  # [{name, type, nullable, cardinality}]
    row_count: int | None
    sampled_at: datetime


@dataclass
class RecordBatch:
    records: list[dict[str, Any]]
    batch_number: int
    total_batches: int | None


class ConnectorBase(ABC):
    """
    Abstract base for all OpenCivic data source connectors.
    Implementors must be stateless between calls.
    Never store decrypted credentials in instance variables after use.
    Never log decrypted config values.
    """

    CONNECTOR_TYPE: str = "base"

    def __init__(self, config: dict[str, Any], connector_id: uuid.UUID) -> None:
        self.connector_id = connector_id
        self._config = config  # Decrypted config — never logged

    @abstractmethod
    async def test_connection(self) -> ConnectionTestResult:
        """Test connectivity. Called before saving connector config."""

    @abstractmethod
    async def get_schema(self) -> SchemaSnapshot:
        """Introspect source schema. Called on first connect and after each pull."""

    @abstractmethod
    async def pull(self, since: datetime | None = None) -> AsyncIterator[RecordBatch]:
        """
        Pull records. since enables incremental load.
        Must yield RecordBatch — never load entire dataset into memory.
        """

    @abstractmethod
    async def close(self) -> None:
        """Clean up. Always called after pull completes or fails."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
