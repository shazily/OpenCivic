"""API rate limit gauges for the developer console."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import ApiKey, UsageEvent


class RateLimitService:
    """Compute per-key usage vs configured limits for the current minute."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def gauges_for_owner(self, owner_id: uuid.UUID) -> list[dict[str, object]]:
        """Return rate-limit gauge rows for API keys owned by a developer."""
        keys = await self._session.scalars(
            select(ApiKey)
            .where(ApiKey.owner_id == owner_id, ApiKey.revoked_at.is_(None))
            .order_by(ApiKey.created_at.desc())
        )
        api_keys = list(keys.all())
        if not api_keys:
            return []

        since = datetime.now(UTC) - timedelta(minutes=1)
        gauges: list[dict[str, object]] = []
        for key in api_keys:
            count = await self._session.scalar(
                select(func.count())
                .select_from(UsageEvent)
                .where(
                    UsageEvent.api_key_id == key.id,
                    UsageEvent.event_type == "api_call",
                    UsageEvent.created_at >= since,
                )
            )
            limit = key.rate_limit_override or settings.DEFAULT_API_RATE_LIMIT_PER_MIN
            used = int(count or 0)
            gauges.append(
                {
                    "api_key_id": str(key.id),
                    "name": key.name,
                    "key_prefix": key.key_prefix,
                    "limit_per_minute": limit,
                    "used_last_minute": used,
                    "remaining": max(0, limit - used),
                    "utilization_pct": round(min(100.0, (used / limit) * 100), 1) if limit else 0.0,
                }
            )
        return gauges
