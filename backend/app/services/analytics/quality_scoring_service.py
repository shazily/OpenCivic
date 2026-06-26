"""Dataset quality scoring — weighted composite 0–100."""

from __future__ import annotations

from decimal import Decimal

from app.db.models import Dataset


def _metadata_completeness(dataset: Dataset) -> float:
    """Fraction of core DCAT-3 metadata fields populated."""
    metadata = dataset.metadata_ or {}
    required = ("publisher", "theme", "language")
    optional = ("contact_point", "issued", "modified", "spatial")
    required_filled = sum(1 for key in required if metadata.get(key))
    optional_filled = sum(1 for key in optional if metadata.get(key))
    base = required_filled / len(required) if required else 0.0
    bonus = optional_filled / len(optional) if optional else 0.0
    return min(1.0, base * 0.75 + bonus * 0.25)


def _freshness_score(dataset: Dataset) -> float:
    if dataset.last_refreshed_at is not None:
        return 1.0
    if dataset.row_count is not None and dataset.row_count > 0:
        return 0.6
    return 0.2


def _schema_score(dataset: Dataset) -> float:
    snapshot = dataset.schema_snapshot or {}
    columns = snapshot.get("columns", [])
    if not columns:
        return 0.0
    if len(columns) >= 2:
        return 1.0
    return 0.7


def _licence_score(dataset: Dataset) -> float:
    return 1.0 if dataset.licence_id else 0.0


def compute_quality_score(dataset: Dataset) -> Decimal:
    """
    Compute weighted quality score for a dataset.
    Dimensions: completeness 40%, freshness 25%, schema 20%, licence 15%.
    """
    completeness = _metadata_completeness(dataset)
    freshness = _freshness_score(dataset)
    schema = _schema_score(dataset)
    licence = _licence_score(dataset)
    composite = (
        completeness * 0.40
        + freshness * 0.25
        + schema * 0.20
        + licence * 0.15
    )
    return Decimal(str(round(composite * 100, 2)))
