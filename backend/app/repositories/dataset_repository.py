"""Dataset persistence layer — SQLAlchemy ORM only."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DatasetNotFound, SlugConflict
from app.db.models import Dataset
from app.schemas.dataset import DatasetCreate, DatasetUpdate


class DatasetRepository:
    """Tenant-scoped dataset CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        tenant_id: uuid.UUID,
        publisher_id: uuid.UUID,
        data: DatasetCreate,
    ) -> Dataset:
        """Create a dataset draft for the authenticated publisher."""
        dataset = Dataset(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            title=data.title,
            slug=data.slug,
            description=data.description,
            access_level=data.access_level,
            licence_id=data.licence_id,
            publisher_id=publisher_id,
            tags=data.tags,
            status="draft",
        )
        self._session.add(dataset)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise SlugConflict(
                message=f"Dataset slug '{data.slug}' already exists for this tenant.",
                field="slug",
            ) from exc
        return dataset

    async def get_by_id(self, dataset_id: uuid.UUID) -> Dataset:
        """Fetch a dataset by primary key within the current tenant RLS context."""
        dataset = await self._session.scalar(select(Dataset).where(Dataset.id == dataset_id))
        if dataset is None:
            raise DatasetNotFound(message="Dataset not found.")
        return dataset

    async def get_for_publisher(self, dataset_id: uuid.UUID, publisher_id: uuid.UUID) -> Dataset:
        """Fetch a dataset only when owned by the given publisher."""
        dataset = await self._session.scalar(
            select(Dataset).where(
                Dataset.id == dataset_id,
                Dataset.publisher_id == publisher_id,
            )
        )
        if dataset is None:
            raise DatasetNotFound(message="Dataset not found.")
        return dataset

    async def apply_ingest_result(
        self,
        dataset: Dataset,
        *,
        schema_snapshot: dict,
        row_count: int,
        file_size_bytes: int,
    ) -> Dataset:
        """Update dataset metadata after a successful ingest."""
        dataset.schema_snapshot = schema_snapshot
        dataset.row_count = row_count
        dataset.file_size_bytes = file_size_bytes
        dataset.last_refreshed_at = datetime.now(UTC)
        from app.services.analytics.quality_scoring_service import compute_quality_score

        dataset.quality_score = compute_quality_score(dataset)
        await self._session.flush()
        return dataset

    async def update_metadata(
        self,
        dataset: Dataset,
        *,
        data: DatasetUpdate,
    ) -> Dataset:
        """Update editable dataset fields for publisher metadata edits."""
        if data.title is not None:
            dataset.title = data.title
        if data.description is not None:
            dataset.description = data.description
        if data.access_level is not None:
            dataset.access_level = data.access_level
        if data.licence_id is not None:
            dataset.licence_id = data.licence_id
        if data.tags is not None:
            dataset.tags = data.tags
        if data.metadata is not None:
            dataset.metadata_ = data.metadata
        await self._session.flush()
        return dataset

    async def published_tag_facets(self, *, limit: int = 30) -> list[dict[str, int | str]]:
        """Aggregate tag counts for published datasets (public catalog facets)."""
        result = await self._session.scalars(
            select(Dataset.tags).where(Dataset.status == "published")
        )
        counts: dict[str, int] = {}
        for tags in result.all():
            for tag in tags or []:
                counts[tag] = counts.get(tag, 0) + 1
        facets = [{"tag": tag, "count": count} for tag, count in counts.items()]
        facets.sort(key=lambda item: (-int(item["count"]), str(item["tag"])))
        return facets[:limit]

    async def list_datasets(
        self,
        *,
        page_size: int = 20,
        cursor: str | None = None,
        status: str | None = None,
        tag: str | None = None,
        sort: str | None = None,
        publisher_id: uuid.UUID | None = None,
    ) -> tuple[list[Dataset], bool, str | None, int]:
        """List datasets with cursor pagination."""
        order_by = self._resolve_sort(sort)
        query = select(Dataset).order_by(*order_by)
        if status:
            query = query.where(Dataset.status == status)
        if tag:
            query = query.where(Dataset.tags.contains([tag]))
        if publisher_id is not None:
            query = query.where(Dataset.publisher_id == publisher_id)

        count_stmt = select(func.count()).select_from(query.subquery())
        total_count = await self._session.scalar(count_stmt) or 0

        if cursor:
            cursor_id = uuid.UUID(cursor)
            anchor = await self._session.scalar(select(Dataset).where(Dataset.id == cursor_id))
            if anchor is not None:
                primary_sort = sort.lstrip("-") if sort else "published_at"
                if primary_sort == "published_at":
                    anchor_ts = anchor.published_at or anchor.created_at
                    query = query.where(
                        (func.coalesce(Dataset.published_at, Dataset.created_at) < anchor_ts)
                        | (
                            (func.coalesce(Dataset.published_at, Dataset.created_at) == anchor_ts)
                            & (Dataset.id < anchor.id)
                        )
                    )
                elif primary_sort == "created_at":
                    query = query.where(
                        (Dataset.created_at < anchor.created_at)
                        | ((Dataset.created_at == anchor.created_at) & (Dataset.id < anchor.id))
                    )
                else:
                    query = query.where(Dataset.id < anchor.id)

        result = await self._session.scalars(query.limit(page_size + 1))
        rows = list(result.all())
        has_more = len(rows) > page_size
        items = rows[:page_size]
        next_cursor = str(items[-1].id) if has_more and items else None
        return items, has_more, next_cursor, int(total_count)

    @staticmethod
    def _resolve_sort(sort: str | None):
        from sqlalchemy import asc, desc

        allowed = {
            "title": Dataset.title,
            "created_at": Dataset.created_at,
            "published_at": Dataset.published_at,
            "quality_score": Dataset.quality_score,
        }
        if not sort:
            return (Dataset.published_at.desc().nullslast(), Dataset.created_at.desc(), Dataset.id.desc())

        descending = sort.startswith("-")
        field_name = sort[1:] if descending else sort
        column = allowed.get(field_name)
        if column is None:
            return (Dataset.published_at.desc().nullslast(), Dataset.created_at.desc(), Dataset.id.desc())
        direction = desc if descending else asc
        return (direction(column).nullslast(), Dataset.id.desc())

    async def refresh_staleness_states(self) -> int:
        """Recompute staleness_state for published datasets in the current tenant."""
        frequency_hours = {
            "daily": 24,
            "weekly": 168,
            "monthly": 720,
        }
        result = await self._session.scalars(select(Dataset).where(Dataset.status == "published"))
        updated = 0
        now = datetime.now(UTC)
        for dataset in result.all():
            hours = frequency_hours.get(dataset.update_frequency or "on_demand")
            if hours is None:
                new_state = "fresh"
            else:
                anchor = dataset.last_refreshed_at or dataset.published_at or dataset.created_at
                age_hours = (now - anchor).total_seconds() / 3600
                if age_hours >= hours * 2:
                    new_state = "stale"
                elif age_hours >= hours:
                    new_state = "possibly_outdated"
                else:
                    new_state = "fresh"
            if dataset.staleness_state != new_state:
                dataset.staleness_state = new_state
                updated += 1
        return updated

    async def decay_stale_quality_scores(self) -> int:
        """Reduce quality_score for datasets marked stale."""
        from decimal import Decimal

        result = await self._session.scalars(
            select(Dataset).where(
                Dataset.status == "published",
                Dataset.staleness_state == "stale",
                Dataset.quality_score.is_not(None),
            )
        )
        updated = 0
        for dataset in result.all():
            current = float(dataset.quality_score or 0)
            decayed = max(0.0, current - 5.0)
            if decayed != current:
                dataset.quality_score = Decimal(str(round(decayed, 2)))
                updated += 1
        return updated
