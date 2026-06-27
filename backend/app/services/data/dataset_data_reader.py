"""Read dataset row data from the latest Parquet snapshot."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DatasetDataNotAvailable, DatasetNotFound
from app.db.models import Dataset, DatasetVersion
from app.services.data.dataset_data_service import query_parquet_page
from app.services.storage.storage_client import StorageClient, get_storage_client


class DatasetDataReader:
    """Load Parquet from object storage and page rows via DuckDB."""

    def __init__(self, session: AsyncSession, storage: StorageClient | None = None) -> None:
        self._session = session
        self._storage = storage or get_storage_client()

    async def read_page(
        self,
        dataset_id: uuid.UUID,
        *,
        page_size: int,
        cursor: str | None,
        fields: str | None,
        sort: str | None,
    ) -> tuple[list[dict], bool, str | None, int, int]:
        """Return data rows, has_more, next_cursor, total_count, version_number."""
        dataset = await self._session.scalar(select(Dataset).where(Dataset.id == dataset_id))
        if dataset is None:
            raise DatasetNotFound(message="Dataset not found.")

        version = await self._session.scalar(
            select(DatasetVersion)
            .where(
                DatasetVersion.dataset_id == dataset_id,
                DatasetVersion.storage_path.is_not(None),
            )
            .order_by(DatasetVersion.version_number.desc())
            .limit(1)
        )
        if version is None or not version.storage_path:
            raise DatasetDataNotAvailable(
                message="Dataset has no ingested data yet.",
            )

        allowed_columns = {
            column["name"]
            for column in (version.schema_snapshot or {}).get("columns", [])
            if isinstance(column, dict) and column.get("name")
        }
        if not allowed_columns:
            raise DatasetDataNotAvailable(message="Dataset schema is not available.")

        offset = 0
        if cursor:
            try:
                offset = int(cursor)
            except ValueError as exc:
                raise DatasetDataNotAvailable(
                    message="Invalid pagination cursor.",
                    field="cursor",
                ) from exc
            if offset < 0:
                raise DatasetDataNotAvailable(
                    message="Invalid pagination cursor.",
                    field="cursor",
                )

        parquet_bytes = await self._storage.get(version.storage_path)
        rows, has_more = query_parquet_page(
            parquet_bytes,
            allowed_columns=allowed_columns,
            page_size=page_size,
            offset=offset,
            fields=fields,
            sort=sort,
        )
        next_cursor = str(offset + page_size) if has_more else None
        total_count = int(version.row_count or dataset.row_count or 0)
        return rows, has_more, next_cursor, total_count, version.version_number
