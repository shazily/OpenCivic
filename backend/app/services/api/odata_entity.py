"""OData 4.0 entity set JSON responses for published datasets."""

from __future__ import annotations

from app.db.models import Dataset


def normalize_entity_set_name(dataset: Dataset) -> str:
    """Return the canonical OData entity set name for a dataset."""
    return dataset.slug.replace("-", "_")


def build_odata_entity_payload(
    *,
    service_root: str,
    entity_set: str,
    rows: list[dict],
    total_count: int,
) -> dict:
    """Build an OData v4 JSON collection response."""
    return {
        "@odata.context": f"{service_root}/$metadata#{entity_set}",
        "@odata.count": total_count,
        "value": rows,
    }


def build_odata_count_payload(*, count: int) -> dict:
    """Build an OData $count response body."""
    return {"@odata.context": "$metadata", "value": count}
