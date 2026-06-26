"""Dataset version persistence — append-only version rows."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DatasetVersion


class DatasetVersionRepository:
    """Create and query immutable dataset version snapshots."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def next_version_number(self, dataset_id: uuid.UUID) -> int:
        """Return the next monotonic version number for a dataset."""
        current_max = await self._session.scalar(
            select(func.max(DatasetVersion.version_number)).where(
                DatasetVersion.dataset_id == dataset_id
            )
        )
        return int(current_max or 0) + 1

    async def create(
        self,
        *,
        tenant_id: uuid.UUID,
        dataset_id: uuid.UUID,
        version_number: int,
        schema_snapshot: dict,
        row_count: int,
        storage_path: str,
        raw_file_path: str,
        published_by: uuid.UUID | None = None,
        change_summary: str | None = None,
    ) -> DatasetVersion:
        """Insert a new dataset version row."""
        version = DatasetVersion(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            dataset_id=dataset_id,
            version_number=version_number,
            schema_snapshot=schema_snapshot,
            row_count=row_count,
            storage_path=storage_path,
            raw_file_path=raw_file_path,
            published_by=published_by,
            change_summary=change_summary,
        )
        self._session.add(version)
        await self._session.flush()
        return version

    async def get_latest(self, dataset_id: uuid.UUID) -> DatasetVersion | None:
        """Return the highest version_number row for a dataset."""
        return await self._session.scalar(
            select(DatasetVersion)
            .where(DatasetVersion.dataset_id == dataset_id)
            .order_by(DatasetVersion.version_number.desc())
            .limit(1)
        )
