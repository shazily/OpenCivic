"""Legacy XLS schema inference tests."""

from unittest.mock import patch

import pandas as pd

from app.services.ingest.schema_inference import infer_tabular_schema


def test_xls_schema_uses_xlrd_engine() -> None:
    dataframe = pd.DataFrame({"name": ["Alpha"], "count": [1]})
    with patch("pandas.read_excel", return_value=dataframe) as mock_read:
        result = infer_tabular_schema(b"fake-xls-bytes", "legacy.xls")

    mock_read.assert_called_once()
    assert mock_read.call_args.kwargs["engine"] == "xlrd"
    assert result.row_count == 1
    assert result.schema_snapshot["columns"][0]["name"] == "name"
