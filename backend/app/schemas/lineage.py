"""Lineage graph API schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class LineageNodeResponse(BaseModel):
    id: uuid.UUID
    type: str
    label: str
    metadata: dict = Field(default_factory=dict, validation_alias="metadata_")
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class LineageEdgeResponse(BaseModel):
    id: uuid.UUID
    from_node_id: uuid.UUID
    to_node_id: uuid.UUID
    relationship: str
    created_at: datetime

    model_config = {"from_attributes": True}


class LineageGraphResponse(BaseModel):
    nodes: list[LineageNodeResponse]
    edges: list[LineageEdgeResponse]
