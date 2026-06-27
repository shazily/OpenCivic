"""Lineage graph persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LineageEdge, LineageNode


class LineageRepository:
    """Build lineage graphs for datasets."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_node(
        self,
        *,
        tenant_id: uuid.UUID,
        node_type: str,
        label: str,
        metadata: dict | None = None,
        node_id: uuid.UUID | None = None,
    ) -> LineageNode:
        if node_id is not None:
            existing = await self._session.scalar(
                select(LineageNode).where(LineageNode.id == node_id)
            )
            if existing is not None:
                return existing
        node = LineageNode(
            id=node_id or uuid.uuid4(),
            tenant_id=tenant_id,
            type=node_type,
            label=label,
            metadata_=metadata or {},
        )
        self._session.add(node)
        await self._session.flush()
        return node

    async def add_edge(
        self,
        *,
        tenant_id: uuid.UUID,
        from_node_id: uuid.UUID,
        to_node_id: uuid.UUID,
        relationship: str,
    ) -> LineageEdge:
        edge = LineageEdge(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            relationship=relationship,
        )
        self._session.add(edge)
        await self._session.flush()
        return edge

    async def get_graph_for_dataset(
        self, dataset_id: uuid.UUID
    ) -> tuple[list[LineageNode], list[LineageEdge]]:
        dataset_nodes = await self._session.scalars(
            select(LineageNode).where(LineageNode.type == "dataset")
        )
        dataset_node = None
        for node in dataset_nodes:
            if str(node.metadata_.get("dataset_id")) == str(dataset_id):
                dataset_node = node
                break
        if dataset_node is None:
            return [], []

        node_ids = {dataset_node.id}
        edges: list[LineageEdge] = []
        frontier = [dataset_node.id]
        while frontier:
            result = await self._session.scalars(
                select(LineageEdge).where(
                    (LineageEdge.from_node_id.in_(frontier))
                    | (LineageEdge.to_node_id.in_(frontier))
                )
            )
            batch = list(result.all())
            edges.extend(batch)
            new_ids: set[uuid.UUID] = set()
            for edge in batch:
                new_ids.add(edge.from_node_id)
                new_ids.add(edge.to_node_id)
            frontier = [node_id for node_id in new_ids if node_id not in node_ids]
            node_ids.update(new_ids)

        nodes_result = await self._session.scalars(
            select(LineageNode).where(LineageNode.id.in_(node_ids))
        )
        return list(nodes_result.all()), edges
