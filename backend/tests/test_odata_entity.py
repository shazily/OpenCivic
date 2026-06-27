"""Unit tests for OData entity set helpers."""

from app.services.api.odata_entity import (
    build_odata_count_payload,
    build_odata_entity_payload,
    normalize_entity_set_name,
)


class _DatasetStub:
    slug = "my-dataset"


def test_normalize_entity_set_name() -> None:
    assert normalize_entity_set_name(_DatasetStub()) == "my_dataset"


def test_build_odata_entity_payload() -> None:
    payload = build_odata_entity_payload(
        service_root="http://example/api/v1/datasets/1/odata",
        entity_set="my_dataset",
        rows=[{"id": "1"}],
        total_count=1,
    )
    assert payload["@odata.count"] == 1
    assert payload["value"] == [{"id": "1"}]
    assert "my_dataset" in payload["@odata.context"]


def test_build_odata_count_payload() -> None:
    payload = build_odata_count_payload(count=42)
    assert payload["value"] == 42
