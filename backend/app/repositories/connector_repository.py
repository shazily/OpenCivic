"""Connector persistence — SQLAlchemy ORM only."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import encrypt
from app.core.errors import ConnectorNotFound
from app.db.models import Connector


class ConnectorRepository:
    """Tenant-scoped connector CRUD and sync scheduling."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, connector_id: uuid.UUID) -> Connector:
        connector = await self._session.scalar(
            select(Connector).where(Connector.id == connector_id)
        )
        if connector is None:
            raise ConnectorNotFound(message="Connector not found.")
        return connector

    async def get_by_dataset_id(self, dataset_id: uuid.UUID) -> Connector | None:
        """Return the connector linked to a dataset, if any."""
        return await self._session.scalar(
            select(Connector).where(Connector.dataset_id == dataset_id).limit(1)
        )

    async def list_all(self) -> list[Connector]:
        result = await self._session.scalars(select(Connector).order_by(Connector.name.asc()))
        return list(result.all())

    async def create(
        self,
        *,
        tenant_id: uuid.UUID,
        name: str,
        type_name: str,
        config: dict,
        created_by: uuid.UUID,
        dataset_id: uuid.UUID | None = None,
        sync_frequency: str | None = "daily",
    ) -> Connector:
        connector = Connector(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            name=name,
            type=type_name,
            config=encrypt(json.dumps(config)),
            status="active",
            sync_frequency=sync_frequency,
            next_sync_at=datetime.now(UTC),
            created_by=created_by,
            dataset_id=dataset_id,
        )
        self._session.add(connector)
        await self._session.flush()
        return connector

    async def get_due_syncs(self, limit: int = 50) -> list[Connector]:
        now = datetime.now(UTC)
        result = await self._session.scalars(
            select(Connector)
            .where(
                Connector.status == "active",
                Connector.circuit_state != "open",
                Connector.next_sync_at.is_not(None),
                Connector.next_sync_at <= now,
            )
            .order_by(Connector.next_sync_at.asc())
            .limit(limit)
        )
        return list(result.all())

    async def get_open_circuits(self) -> list[Connector]:
        result = await self._session.scalars(
            select(Connector).where(Connector.circuit_state == "open")
        )
        return list(result.all())

    async def mark_sync_success(self, connector_id: uuid.UUID) -> None:
        next_sync = datetime.now(UTC) + timedelta(hours=24)
        await self._session.execute(
            update(Connector)
            .where(Connector.id == connector_id)
            .values(
                last_sync_at=datetime.now(UTC),
                next_sync_at=next_sync,
                failure_count=0,
                circuit_state="closed",
            )
        )

    async def mark_sync_failure(self, connector_id: uuid.UUID, threshold: int) -> None:
        connector = await self.get_by_id(connector_id)
        failures = connector.failure_count + 1
        circuit_state = "open" if failures >= threshold else connector.circuit_state
        await self._session.execute(
            update(Connector)
            .where(Connector.id == connector_id)
            .values(failure_count=failures, circuit_state=circuit_state)
        )

    async def close_circuit(self, connector_id: uuid.UUID) -> None:
        await self._session.execute(
            update(Connector)
            .where(Connector.id == connector_id)
            .values(circuit_state="closed", failure_count=0)
        )
