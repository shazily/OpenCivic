"""Record lineage nodes and edges for ingest and connector events."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.lineage_repository import LineageRepository


class LineageService:
    """Create lineage graph entries for datasets."""

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self._repo = LineageRepository(session)
        self._tenant_id = tenant_id

    async def record_upload_ingest(
        self,
        *,
        dataset_id: uuid.UUID,
        filename: str,
        version_number: int,
        storage_key: str,
    ) -> None:
        source = await self._repo.upsert_node(
            tenant_id=self._tenant_id,
            node_type="source",
            label=filename,
            metadata={"storage_key": storage_key, "kind": "upload"},
        )
        dataset_node = await self._repo.upsert_node(
            tenant_id=self._tenant_id,
            node_type="dataset",
            label=str(dataset_id),
            metadata={"dataset_id": str(dataset_id)},
        )
        version_node = await self._repo.upsert_node(
            tenant_id=self._tenant_id,
            node_type="version",
            label=f"v{version_number}",
            metadata={"dataset_id": str(dataset_id), "version_number": version_number},
        )
        await self._repo.add_edge(
            tenant_id=self._tenant_id,
            from_node_id=source.id,
            to_node_id=dataset_node.id,
            relationship="derived_from",
        )
        await self._repo.add_edge(
            tenant_id=self._tenant_id,
            from_node_id=dataset_node.id,
            to_node_id=version_node.id,
            relationship="published_as",
        )

    async def record_connector_sync(
        self,
        *,
        connector_id: uuid.UUID,
        connector_name: str,
        dataset_id: uuid.UUID,
    ) -> None:
        connector_node = await self._repo.upsert_node(
            tenant_id=self._tenant_id,
            node_type="connector",
            label=connector_name,
            metadata={"connector_id": str(connector_id)},
        )
        dataset_node = await self._repo.upsert_node(
            tenant_id=self._tenant_id,
            node_type="dataset",
            label=str(dataset_id),
            metadata={"dataset_id": str(dataset_id)},
        )
        await self._repo.add_edge(
            tenant_id=self._tenant_id,
            from_node_id=connector_node.id,
            to_node_id=dataset_node.id,
            relationship="refreshed_from",
        )
