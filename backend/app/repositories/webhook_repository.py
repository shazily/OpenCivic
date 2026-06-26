"""Webhook persistence — SQLAlchemy ORM only."""

from __future__ import annotations

import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import encrypt
from app.core.errors import ValidationError
from app.db.models import Webhook

ALLOWED_EVENTS = frozenset(
    {
        "DatasetPublished",
        "DatasetRejected",
        "DatasetSubmitted",
        "DatasetArchived",
        "DatasetScheduled",
    }
)


class WebhookRepository:
    """Tenant-scoped webhook CRUD."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_owner(self, owner_id: uuid.UUID) -> list[Webhook]:
        result = await self._session.scalars(
            select(Webhook)
            .where(Webhook.created_by == owner_id)
            .order_by(Webhook.created_at.desc())
        )
        return list(result.all())

    async def get_for_owner(self, webhook_id: uuid.UUID, owner_id: uuid.UUID) -> Webhook:
        webhook = await self._session.scalar(
            select(Webhook).where(Webhook.id == webhook_id, Webhook.created_by == owner_id)
        )
        if webhook is None:
            raise ValidationError(message="Webhook not found.", field="id")
        return webhook

    async def create(
        self,
        *,
        tenant_id: uuid.UUID,
        owner_id: uuid.UUID,
        url: str,
        events: list[str],
        dataset_id: uuid.UUID | None = None,
    ) -> Webhook:
        invalid = [event for event in events if event not in ALLOWED_EVENTS]
        if invalid:
            raise ValidationError(
                message=f"Invalid events: {', '.join(invalid)}",
                field="events",
            )
        signing_secret = secrets.token_urlsafe(32)
        webhook = Webhook(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            url=url,
            secret=encrypt(signing_secret),
            events=events,
            dataset_id=dataset_id,
            created_by=owner_id,
        )
        self._session.add(webhook)
        await self._session.flush()
        return webhook

    async def delete(self, webhook_id: uuid.UUID, owner_id: uuid.UUID) -> None:
        webhook = await self.get_for_owner(webhook_id, owner_id)
        await self._session.delete(webhook)
