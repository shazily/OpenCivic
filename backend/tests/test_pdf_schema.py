"""PDF schema inference tests."""

from unittest.mock import MagicMock, patch

from app.services.ingest.schema_inference import InferredSchema, infer_tabular_schema


def test_pdf_schema_inference_from_table() -> None:
    inferred = InferredSchema(
        schema_snapshot={"columns": [{"name": "name", "type": "string", "nullable": False}]},
        row_count=2,
        dataframe=MagicMock(),
    )
    with patch(
        "app.services.ingest.schema_inference._infer_pdf_schema",
        return_value=inferred,
    ):
        result = infer_tabular_schema(b"%PDF-fake", "report.pdf")

    assert result.row_count == 2
    assert result.schema_snapshot["columns"][0]["name"] == "name"
