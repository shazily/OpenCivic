"""CQRS event store reads — SQLAlchemy ORM only."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Dataset, Event


class EventRepository:
    """Read-only queries against the append-only events table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_dataset(
        self,
        dataset_id: uuid.UUID,
        *,
        limit: int = 20,
    ) -> list[Event]:
        result = await self._session.scalars(
            select(Event)
            .where(Event.aggregate_id == dataset_id, Event.aggregate_type == "dataset")
            .order_by(Event.created_at.desc(), Event.id.desc())
            .limit(limit)
        )
        return list(result.all())

    async def list_for_publisher(
        self,
        publisher_id: uuid.UUID,
        *,
        limit: int = 25,
    ) -> list[Event]:
        result = await self._session.scalars(
            select(Event)
            .join(Dataset, Dataset.id == Event.aggregate_id)
            .where(
                Event.aggregate_type == "dataset",
                Dataset.publisher_id == publisher_id,
            )
            .order_by(Event.created_at.desc(), Event.id.desc())
            .limit(limit)
        )
        return list(result.all())
