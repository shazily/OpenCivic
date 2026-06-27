"""Postgres full-text and pg_trgm fuzzy search for datasets."""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Dataset
from app.services.search.qdrant_service import semantic_dataset_ids


def _relevance_score(term: str):
    """Trigram similarity score for title and description."""
    title_similarity = func.similarity(Dataset.title, term)
    description_similarity = func.similarity(func.coalesce(Dataset.description, ""), term)
    return func.greatest(title_similarity, description_similarity)


class SearchService:
    """Tier-2 dataset search backed by Postgres pg_trgm similarity."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search_datasets(
        self,
        query: str,
        *,
        page_size: int = 20,
        cursor: str | None = None,
        licence_id: uuid.UUID | None = None,
        status: str | None = None,
        tag: str | None = None,
        tenant_id: uuid.UUID | None = None,
    ) -> tuple[list[Dataset], bool, str | None, int]:
        """Search datasets by title, description, tags, and optional Qdrant semantic hits."""
        term = query.strip()
        semantic_ids: list[uuid.UUID] = []
        if tenant_id is not None:
            semantic_ids = await semantic_dataset_ids(tenant_id, term, limit=page_size)

        relevance = _relevance_score(term)

        filters = or_(
            Dataset.title.ilike(f"%{term}%"),
            Dataset.description.ilike(f"%{term}%"),
            func.array_to_string(Dataset.tags, " ").ilike(f"%{term}%"),
            relevance >= 0.2,
        )
        if semantic_ids:
            filters = or_(filters, Dataset.id.in_(semantic_ids))

        stmt = select(Dataset).where(filters)
        if licence_id is not None:
            stmt = stmt.where(Dataset.licence_id == licence_id)
        if status is not None:
            stmt = stmt.where(Dataset.status == status)
        if tag is not None:
            stmt = stmt.where(Dataset.tags.contains([tag]))

        stmt = stmt.order_by(relevance.desc(), Dataset.created_at.desc(), Dataset.id.desc())

        if cursor:
            cursor_id = uuid.UUID(cursor)
            anchor = await self._session.scalar(select(Dataset).where(Dataset.id == cursor_id))
            if anchor is not None:
                anchor_relevance = func.greatest(
                    func.similarity(anchor.title, term),
                    func.similarity(func.coalesce(anchor.description, ""), term),
                )
                stmt = stmt.where(
                    (relevance < anchor_relevance)
                    | (
                        (relevance == anchor_relevance)
                        & (
                            (Dataset.created_at < anchor.created_at)
                            | (
                                (Dataset.created_at == anchor.created_at)
                                & (Dataset.id < anchor.id)
                            )
                        )
                    )
                )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_count = await self._session.scalar(count_stmt) or 0

        result = await self._session.scalars(stmt.limit(page_size + 1))
        rows = list(result.all())
        has_more = len(rows) > page_size
        items = rows[:page_size]
        next_cursor = str(items[-1].id) if has_more and items else None
        return items, has_more, next_cursor, int(total_count)
