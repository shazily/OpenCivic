"""Quality scoring service tests."""

from decimal import Decimal

import pytest

from app.db.models import Dataset
from app.services.analytics.quality_scoring_service import compute_quality_score


def test_quality_score_increases_with_metadata() -> None:
    import uuid

    sparse = Dataset(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        title="Test",
        slug="test",
        publisher_id=uuid.uuid4(),
        schema_snapshot={"columns": [{"name": "a", "type": "string"}]},
        row_count=10,
    )
    rich = Dataset(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        title="Test",
        slug="test-rich",
        publisher_id=uuid.uuid4(),
        licence_id=uuid.uuid4(),
        schema_snapshot={
            "columns": [
                {"name": "a", "type": "string"},
                {"name": "b", "type": "integer"},
            ]
        },
        row_count=100,
        metadata_={"publisher": "NSO", "theme": "economy", "language": "en"},
    )
    assert compute_quality_score(rich) > compute_quality_score(sparse)
    assert compute_quality_score(rich) <= Decimal("100")
