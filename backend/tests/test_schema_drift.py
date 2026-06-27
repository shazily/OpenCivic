"""Schema drift detection tests."""

from app.services.ingest.schema_drift_service import detect_schema_drift


def test_no_drift_on_first_schema() -> None:
    incoming = {"columns": [{"name": "a", "type": "string"}]}
    result = detect_schema_drift(None, incoming)
    assert result.has_drift is False


def test_detects_added_column() -> None:
    previous = {"columns": [{"name": "a", "type": "string"}]}
    incoming = {
        "columns": [
            {"name": "a", "type": "string"},
            {"name": "b", "type": "integer"},
        ]
    }
    result = detect_schema_drift(previous, incoming)
    assert result.has_drift is True
    assert result.added_columns == ("b",)


def test_detects_type_change() -> None:
    previous = {"columns": [{"name": "a", "type": "string"}]}
    incoming = {"columns": [{"name": "a", "type": "integer"}]}
    result = detect_schema_drift(previous, incoming)
    assert result.has_drift is True
    assert result.type_changes[0][0] == "a"
