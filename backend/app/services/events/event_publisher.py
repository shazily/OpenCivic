"""CQRS event publisher — append-only writes to the events table."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Event


class EventPublisher:
    """Insert immutable domain events for audit and projections."""

    @staticmethod
    async def publish(
        session: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        event_type: str,
        aggregate_id: uuid.UUID,
        aggregate_type: str,
        actor_id: uuid.UUID | None,
        actor_type: str = "user",
        payload: dict | None = None,
    ) -> Event:
        """Record a new event in the append-only store."""
        event = Event(
            tenant_id=tenant_id,
            event_type=event_type,
            aggregate_id=aggregate_id,
            aggregate_type=aggregate_type,
            actor_id=actor_id,
            actor_type=actor_type,
            payload=payload or {},
        )
        session.add(event)
        await session.flush()
        return event
