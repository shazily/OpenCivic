"""Generate OpenAPI 3.1 spec for a published dataset data endpoint."""

from __future__ import annotations

from typing import Any

from app.db.models import Dataset

DEFAULT_API_BASE = "http://127.0.0.1:8100"


def _column_schema(column: dict[str, Any]) -> dict[str, Any]:
    dtype = column.get("type", "string")
    mapping: dict[str, dict[str, Any]] = {
        "integer": {"type": "integer"},
        "float": {"type": "number"},
        "boolean": {"type": "boolean"},
        "datetime": {"type": "string", "format": "date-time"},
        "date": {"type": "string", "format": "date"},
    }
    return mapping.get(dtype, {"type": "string"})


def build_dataset_openapi(dataset: Dataset, base_url: str | None = None) -> dict[str, Any]:
    """Build a per-dataset OpenAPI 3.1 document for the REST data API."""
    api_root = (base_url or DEFAULT_API_BASE).rstrip("/")
    dataset_id = str(dataset.id)
    columns = (dataset.schema_snapshot or {}).get("columns", [])
    row_properties: dict[str, Any] = {}
    for column in columns:
        name = column.get("name")
        if not name:
            continue
        row_properties[name] = _column_schema(column)

    data_path = f"/api/v1/datasets/{dataset_id}/data"
    return {
        "openapi": "3.1.0",
        "info": {
            "title": dataset.title,
            "description": dataset.description or f"OpenCivic dataset {dataset.slug}",
            "version": "1.0.0",
        },
        "servers": [{"url": api_root}],
        "paths": {
            data_path: {
                "get": {
                    "operationId": "listDatasetRows",
                    "summary": f"List rows from {dataset.title}",
                    "parameters": [
                        {
                            "name": "page_size",
                            "in": "query",
                            "schema": {"type": "integer", "maximum": 10000, "default": 100},
                        },
                        {
                            "name": "cursor",
                            "in": "query",
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "sort",
                            "in": "query",
                            "schema": {"type": "string"},
                            "description": "Sort field; prefix with - for descending.",
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Paginated dataset rows",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "data": {
                                                "type": "array",
                                                "items": {
                                                    "type": "object",
                                                    "properties": row_properties,
                                                    "additionalProperties": True,
                                                },
                                            },
                                            "meta": {
                                                "type": "object",
                                                "properties": {
                                                    "has_more": {"type": "boolean"},
                                                    "next_cursor": {"type": "string", "nullable": True},
                                                    "total_count": {"type": "integer", "nullable": True},
                                                },
                                            },
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            }
        },
    }
