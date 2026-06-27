"""Valkey-cached instant search for Cmd+K command palette."""

from __future__ import annotations

import hashlib
import json
import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get, cache_set
from app.db.models import Dataset

CACHE_TTL_SECONDS = 60


def _cache_key(tenant_id: uuid.UUID, query: str) -> str:
    digest = hashlib.sha256(query.strip().lower().encode()).hexdigest()[:16]
    return f"palette:{tenant_id}:{digest}"


class CommandPaletteService:
    """Tier-1 palette search — Valkey cache with Postgres fallback."""

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def search(self, query: str, *, limit: int = 8) -> list[dict[str, str]]:
        """Return lightweight dataset hits for the command palette."""
        term = query.strip()
        if not term:
            return []

        key = _cache_key(self._tenant_id, term)
        cached = await cache_get(key)
        if cached:
            return json.loads(cached)

        filters = or_(
            Dataset.title.ilike(f"%{term}%"),
            Dataset.slug.ilike(f"%{term}%"),
            Dataset.tags.contains([term]),
        )
        result = await self._session.scalars(
            select(Dataset)
            .where(Dataset.status == "published", filters)
            .order_by(Dataset.published_at.desc().nullslast(), Dataset.title.asc())
            .limit(limit)
        )
        hits = [
            {
                "id": str(item.id),
                "title": item.title,
                "slug": item.slug,
                "type": "exact",
                "tier": "keyword",
            }
            for item in result.all()
        ]

        existing_ids = {hit["id"] for hit in hits}
        try:
            from app.services.search.qdrant_service import semantic_dataset_ids

            semantic_ids = await semantic_dataset_ids(self._tenant_id, term, limit=limit)
            if semantic_ids:
                semantic_rows = await self._session.scalars(
                    select(Dataset)
                    .where(Dataset.id.in_(semantic_ids), Dataset.status == "published")
                    .limit(limit)
                )
                for item in semantic_rows.all():
                    item_id = str(item.id)
                    if item_id in existing_ids:
                        continue
                    hits.append(
                        {
                            "id": item_id,
                            "title": item.title,
                            "slug": item.slug,
                            "type": "related",
                            "tier": "semantic",
                        }
                    )
                    existing_ids.add(item_id)
        except Exception:
            pass

        await cache_set(key, json.dumps(hits), ttl_seconds=CACHE_TTL_SECONDS)
        return hits
