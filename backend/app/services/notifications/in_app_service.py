"""Valkey-backed in-app notifications for staff consoles."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from app.core.cache import get_cache

MAX_NOTIFICATIONS = 100
NOTIFICATION_TTL_SECONDS = 90 * 86_400


def _list_key(tenant_id: uuid.UUID, user_id: uuid.UUID) -> str:
    return f"notify:{tenant_id}:{user_id}"


class InAppNotificationService:
    """Push and list ephemeral notifications without a Postgres table (v1)."""

    @staticmethod
    async def push(
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        title: str,
        body: str,
        event_type: str,
        link: str | None = None,
    ) -> dict[str, str]:
        """Append a notification for a user."""
        client = await get_cache()
        item = {
            "id": str(uuid.uuid4()),
            "title": title,
            "body": body,
            "event_type": event_type,
            "link": link,
            "read": False,
            "created_at": datetime.now(UTC).isoformat(),
        }
        key = _list_key(tenant_id, user_id)
        await client.lpush(key, json.dumps(item))
        await client.ltrim(key, 0, MAX_NOTIFICATIONS - 1)
        await client.expire(key, NOTIFICATION_TTL_SECONDS)
        return item

    @staticmethod
    async def list_for_user(
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        limit: int = 20,
    ) -> list[dict[str, object]]:
        """Return recent notifications newest-first."""
        client = await get_cache()
        key = _list_key(tenant_id, user_id)
        raw_items = await client.lrange(key, 0, max(limit - 1, 0))
        notifications: list[dict[str, object]] = []
        for raw in raw_items:
            try:
                notifications.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
        return notifications

    @staticmethod
    async def unread_count(tenant_id: uuid.UUID, user_id: uuid.UUID) -> int:
        items = await InAppNotificationService.list_for_user(
            tenant_id,
            user_id,
            limit=MAX_NOTIFICATIONS,
        )
        return sum(1 for item in items if not item.get("read"))

    @staticmethod
    async def mark_read(
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        notification_id: str,
    ) -> bool:
        """Mark a single notification as read. Returns False if not found."""
        client = await get_cache()
        key = _list_key(tenant_id, user_id)
        raw_items = await client.lrange(key, 0, MAX_NOTIFICATIONS - 1)
        updated: list[str] = []
        found = False
        for raw in raw_items:
            try:
                item = json.loads(raw)
            except json.JSONDecodeError:
                updated.append(raw)
                continue
            if item.get("id") == notification_id and not item.get("read"):
                item["read"] = True
                found = True
            updated.append(json.dumps(item))
        if found:
            await client.delete(key)
            if updated:
                await client.rpush(key, *reversed(updated))
                await client.expire(key, NOTIFICATION_TTL_SECONDS)
        return found

    @staticmethod
    async def mark_all_read(tenant_id: uuid.UUID, user_id: uuid.UUID) -> int:
        """Mark all notifications read. Returns count updated."""
        client = await get_cache()
        key = _list_key(tenant_id, user_id)
        raw_items = await client.lrange(key, 0, MAX_NOTIFICATIONS - 1)
        updated: list[str] = []
        count = 0
        for raw in raw_items:
            try:
                item = json.loads(raw)
            except json.JSONDecodeError:
                updated.append(raw)
                continue
            if not item.get("read"):
                item["read"] = True
                count += 1
            updated.append(json.dumps(item))
        if count:
            await client.delete(key)
            if updated:
                await client.rpush(key, *reversed(updated))
                await client.expire(key, NOTIFICATION_TTL_SECONDS)
        return count
