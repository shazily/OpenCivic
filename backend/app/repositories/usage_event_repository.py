"""Usage event persistence — SQLAlchemy ORM only."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UsageEvent, UsageHourlyRollup


class UsageEventRepository:
    """Tenant-scoped usage event writes and aggregates."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        tenant_id: uuid.UUID,
        event_type: str,
        dataset_id: uuid.UUID | None = None,
        actor_id: uuid.UUID | None = None,
        api_key_id: uuid.UUID | None = None,
        format_name: str | None = None,
        bytes_count: int | None = None,
        response_ms: int | None = None,
    ) -> UsageEvent:
        event = UsageEvent(
            tenant_id=tenant_id,
            dataset_id=dataset_id,
            event_type=event_type,
            actor_id=actor_id,
            api_key_id=api_key_id,
            format=format_name,
            bytes=bytes_count,
            response_ms=response_ms,
        )
        self._session.add(event)
        await self._session.flush()
        return event

    async def count_by_type(self, dataset_id: uuid.UUID, event_type: str) -> int:
        count = await self._session.scalar(
            select(func.count())
            .select_from(UsageEvent)
            .where(UsageEvent.dataset_id == dataset_id, UsageEvent.event_type == event_type)
        )
        return int(count or 0)

    async def counts_for_dataset(self, dataset_id: uuid.UUID) -> dict[str, int]:
        result = await self._session.execute(
            select(UsageEvent.event_type, func.count())
            .where(UsageEvent.dataset_id == dataset_id)
            .group_by(UsageEvent.event_type)
        )
        return {row[0]: int(row[1]) for row in result.all()}

    async def daily_engagement_trend(
        self,
        dataset_id: uuid.UUID,
        *,
        days: int = 14,
    ) -> list[dict[str, object]]:
        """Daily view and download counts for sparkline charts."""
        cutoff = datetime.now(UTC) - timedelta(days=days - 1)
        day_bucket = func.date_trunc("day", UsageEvent.created_at)
        result = await self._session.execute(
            select(day_bucket.label("day"), UsageEvent.event_type, func.count())
            .where(
                UsageEvent.dataset_id == dataset_id,
                UsageEvent.event_type.in_(("view", "download")),
                UsageEvent.created_at >= cutoff,
            )
            .group_by(day_bucket, UsageEvent.event_type)
            .order_by(day_bucket.asc())
        )
        by_day: dict[str, dict[str, int]] = {}
        for day_value, event_type, count in result.all():
            day_key = day_value.date().isoformat()
            bucket = by_day.setdefault(day_key, {"views": 0, "downloads": 0})
            if event_type == "view":
                bucket["views"] = int(count)
            elif event_type == "download":
                bucket["downloads"] = int(count)

        trend: list[dict[str, object]] = []
        today = datetime.now(UTC).date()
        for offset in range(days - 1, -1, -1):
            day = today - timedelta(days=offset)
            day_key = day.isoformat()
            counts = by_day.get(day_key, {"views": 0, "downloads": 0})
            trend.append(
                {
                    "date": day_key,
                    "views": counts["views"],
                    "downloads": counts["downloads"],
                    "total": counts["views"] + counts["downloads"],
                }
            )
        return trend

    async def publisher_totals(self, publisher_id: uuid.UUID) -> dict[str, int]:
        """Aggregate usage events across all datasets owned by a publisher."""
        from app.db.models import Dataset

        result = await self._session.execute(
            select(UsageEvent.event_type, func.count())
            .join(Dataset, Dataset.id == UsageEvent.dataset_id)
            .where(Dataset.publisher_id == publisher_id)
            .group_by(UsageEvent.event_type)
        )
        totals = {row[0]: int(row[1]) for row in result.all()}
        return {
            "views": totals.get("view", 0),
            "downloads": totals.get("download", 0),
            "api_calls": totals.get("api_call", 0),
            "ai_queries": totals.get("ai_query", 0),
        }

    async def tenant_totals(self) -> dict[str, int]:
        """Aggregate usage events across the entire tenant (RLS-scoped session)."""
        result = await self._session.execute(
            select(UsageEvent.event_type, func.count()).group_by(UsageEvent.event_type)
        )
        totals = {row[0]: int(row[1]) for row in result.all()}
        return {
            "views": totals.get("view", 0),
            "downloads": totals.get("download", 0),
            "api_calls": totals.get("api_call", 0),
            "ai_queries": totals.get("ai_query", 0),
        }

    async def rollup_hourly(self, lookback_hours: int = 48) -> int:
        """Aggregate raw usage_events into usage_hourly_rollups for recent hours."""
        cutoff = datetime.now(UTC) - timedelta(hours=lookback_hours)
        hour_bucket = func.date_trunc("hour", UsageEvent.created_at)
        result = await self._session.execute(
            select(
                UsageEvent.tenant_id,
                UsageEvent.dataset_id,
                UsageEvent.event_type,
                hour_bucket.label("hour_bucket"),
                func.count().label("event_count"),
                func.coalesce(func.sum(UsageEvent.bytes), 0).label("bytes_total"),
            )
            .where(UsageEvent.created_at >= cutoff)
            .group_by(
                UsageEvent.tenant_id,
                UsageEvent.dataset_id,
                UsageEvent.event_type,
                hour_bucket,
            )
        )
        rows = result.all()
        upserted = 0
        for row in rows:
            stmt = (
                pg_insert(UsageHourlyRollup)
                .values(
                    tenant_id=row.tenant_id,
                    dataset_id=row.dataset_id,
                    event_type=row.event_type,
                    hour_bucket=row.hour_bucket,
                    event_count=row.event_count,
                    bytes_total=int(row.bytes_total or 0),
                )
                .on_conflict_do_update(
                    index_elements=[
                        "tenant_id",
                        "dataset_id",
                        "event_type",
                        "hour_bucket",
                    ],
                    set_={
                        "event_count": row.event_count,
                        "bytes_total": int(row.bytes_total or 0),
                    },
                )
            )
            await self._session.execute(stmt)
            upserted += 1
        return upserted
