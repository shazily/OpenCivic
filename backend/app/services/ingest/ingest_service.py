"""Orchestrates upload ingest: scan, infer schema, Parquet, DB update, event."""

import uuid

import structlog

from app.core.errors import StorageError, SchemaDriftDetected
from app.db.session import tenant_write_session
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.dataset_version_repository import DatasetVersionRepository
from app.services.events.event_publisher import EventPublisher
from app.services.ingest.parquet_converter import (
    dataframe_to_parquet_bytes,
    parquet_storage_key,
)
from app.services.ingest.schema_drift_service import detect_schema_drift
from app.services.ingest.schema_inference import infer_tabular_schema
from app.services.ingest.virus_scanner import scan_bytes
from app.services.lineage.lineage_service import LineageService
from app.services.storage.storage_client import StorageClient, get_storage_client

logger = structlog.get_logger(__name__)


class IngestService:
    """Run the full ingest pipeline for a raw upload in object storage."""

    def __init__(self, storage: StorageClient | None = None) -> None:
        self._storage = storage or get_storage_client()

    async def run(
        self,
        *,
        tenant_id: uuid.UUID,
        dataset_id: uuid.UUID,
        storage_key: str,
        filename: str,
        publisher_id: uuid.UUID | None = None,
    ) -> dict:
        """
        Download raw file, scan, infer schema, write Parquet, persist version row,
        update dataset metadata, and emit DatasetIngested.
        """
        try:
            raw_bytes = await self._storage.get(storage_key)
        except Exception as exc:
            raise StorageError(message="Failed to read uploaded file from storage.") from exc

        scan_bytes(raw_bytes)
        inferred = infer_tabular_schema(raw_bytes, filename)

        async with tenant_write_session(tenant_id) as session:
            dataset_repo = DatasetRepository(session)
            version_repo = DatasetVersionRepository(session)
            dataset = await dataset_repo.get_by_id(dataset_id)
            latest_version = await version_repo.get_latest(dataset_id)
            if latest_version is not None:
                drift = detect_schema_drift(
                    latest_version.schema_snapshot,
                    inferred.schema_snapshot,
                )
                if drift.has_drift:
                    dataset.staleness_state = "pending_refresh"
                    await session.flush()
                    await EventPublisher.publish(
                        session,
                        tenant_id=tenant_id,
                        event_type="SchemaDriftDetected",
                        aggregate_id=dataset_id,
                        aggregate_type="dataset",
                        actor_id=publisher_id,
                        actor_type="user" if publisher_id else "system",
                        payload={
                            "added_columns": list(drift.added_columns),
                            "removed_columns": list(drift.removed_columns),
                            "type_changes": [
                                {"column": name, "from": old, "to": new}
                                for name, old, new in drift.type_changes
                            ],
                        },
                    )
                    raise SchemaDriftDetected(
                        message="Schema drift detected — review required before ingest proceeds.",
                        detail={
                            "added_columns": list(drift.added_columns),
                            "removed_columns": list(drift.removed_columns),
                            "type_changes": [
                                {"column": name, "from": old, "to": new}
                                for name, old, new in drift.type_changes
                            ],
                        },
                    )

            version_number = await version_repo.next_version_number(dataset_id)
            parquet_key = parquet_storage_key(tenant_id, dataset_id, version_number)
            parquet_bytes = dataframe_to_parquet_bytes(inferred.dataframe)
            await self._storage.put(
                parquet_key,
                parquet_bytes,
                content_type="application/octet-stream",
            )

            await version_repo.create(
                tenant_id=tenant_id,
                dataset_id=dataset_id,
                version_number=version_number,
                schema_snapshot=inferred.schema_snapshot,
                row_count=inferred.row_count,
                storage_path=parquet_key,
                raw_file_path=storage_key,
                published_by=publisher_id,
                change_summary="Initial upload ingest",
            )
            await dataset_repo.apply_ingest_result(
                dataset,
                schema_snapshot=inferred.schema_snapshot,
                row_count=inferred.row_count,
                file_size_bytes=len(raw_bytes),
            )
            await EventPublisher.publish(
                session,
                tenant_id=tenant_id,
                event_type="DatasetIngested",
                aggregate_id=dataset_id,
                aggregate_type="dataset",
                actor_id=publisher_id,
                actor_type="user" if publisher_id else "system",
                payload={
                    "version_number": version_number,
                    "row_count": inferred.row_count,
                    "storage_key": storage_key,
                    "parquet_key": parquet_key,
                },
            )
            await LineageService(session, tenant_id).record_upload_ingest(
                dataset_id=dataset_id,
                filename=filename,
                version_number=version_number,
                storage_key=storage_key,
            )

        logger.info(
            "ingest_completed",
            dataset_id=str(dataset_id),
            version_number=version_number,
            row_count=inferred.row_count,
        )
        return {
            "status": "success",
            "dataset_id": str(dataset_id),
            "version_number": version_number,
            "row_count": inferred.row_count,
        }
