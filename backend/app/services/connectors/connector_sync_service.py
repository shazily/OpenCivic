"""Connector sync orchestration."""

from __future__ import annotations

import uuid

import structlog

from app.core.config import settings
from app.repositories.connector_repository import ConnectorRepository
from app.repositories.dataset_repository import DatasetRepository
from app.services.connectors.base import ConnectorBase
from app.services.connectors.registry import get_connector
from app.services.ingest.ingest_service import IngestService
from app.services.ingest.upload_validation import raw_storage_key
from app.services.lineage.lineage_service import LineageService
from app.services.storage.storage_client import get_storage_client

logger = structlog.get_logger(__name__)


class ConnectorSyncService:
    """Pull from a connector and run the ingest pipeline."""

    async def run(self, session, tenant_id: uuid.UUID, connector_id: uuid.UUID) -> dict:
        repo = ConnectorRepository(session)
        connector = await repo.get_by_id(connector_id)
        config = ConnectorBase.parse_config(connector.config)
        plugin = get_connector(connector.type, config)

        test = await plugin.test_connection()
        if not test.ok:
            await repo.mark_sync_failure(
                connector_id,
                settings.CONNECTOR_CIRCUIT_BREAKER_THRESHOLD,
            )
            return {"status": "error", "message": test.message}

        if connector.dataset_id is None:
            await repo.mark_sync_success(connector_id)
            return {"status": "skipped", "reason": "no_dataset_linked"}

        dataset = await DatasetRepository(session).get_by_id(connector.dataset_id)
        batches = []
        async for batch in plugin.pull(connector.last_sync_at):
            batches.append(batch)
        rows: list[dict] = []
        schema = None
        for batch in batches:
            rows.extend(batch.rows)
            if batch.schema is not None:
                schema = batch.schema
        if not rows:
            await repo.mark_sync_success(connector_id)
            return {"status": "ok", "row_count": 0}

        import pandas as pd

        from app.core.errors import SchemaDriftDetected
        from app.repositories.dataset_version_repository import DatasetVersionRepository
        from app.services.ingest.schema_drift_service import detect_schema_drift
        from app.services.ingest.schema_inference import infer_tabular_schema

        frame = pd.DataFrame(rows)
        csv_bytes = frame.to_csv(index=False).encode("utf-8")
        inferred = infer_tabular_schema(csv_bytes, "connector-pull.csv")
        version_repo = DatasetVersionRepository(session)
        latest = await version_repo.get_latest(dataset.id)
        if latest is not None:
            drift = detect_schema_drift(latest.schema_snapshot, inferred.schema_snapshot)
            if drift.has_drift:
                dataset.staleness_state = "pending_refresh"
                await session.flush()
                raise SchemaDriftDetected(
                    message="Connector pull schema drift — approval required.",
                    detail={
                        "added_columns": list(drift.added_columns),
                        "removed_columns": list(drift.removed_columns),
                    },
                )

        storage = get_storage_client()
        upload_id = uuid.uuid4()
        storage_key = raw_storage_key(tenant_id, dataset.id, upload_id, "csv")
        await storage.put(storage_key, csv_bytes, content_type="text/csv")

        await IngestService(storage=storage).run(
            tenant_id=tenant_id,
            dataset_id=dataset.id,
            storage_key=storage_key,
            filename="connector-pull.csv",
            publisher_id=connector.created_by,
        )
        await LineageService(session, tenant_id).record_connector_sync(
            connector_id=connector.id,
            connector_name=connector.name,
            dataset_id=dataset.id,
        )
        await repo.mark_sync_success(connector_id)
        logger.info(
            "connector_sync_completed",
            connector_id=str(connector_id),
            row_count=len(rows),
            schema_columns=len(schema.columns) if schema else 0,
        )
        return {"status": "ok", "row_count": len(rows)}
