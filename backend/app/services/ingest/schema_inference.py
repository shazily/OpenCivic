"""CSV/TSV/JSON/JSONL/XLSX/Parquet/PDF schema inference using chardet and pandas."""

import io
from dataclasses import dataclass

import chardet
import pandas as pd

from app.core.errors import InvalidFileFormat, SchemaInferenceError


@dataclass(frozen=True)
class InferredSchema:
    """Result of schema inference on tabular upload data."""

    schema_snapshot: dict
    row_count: int
    dataframe: pd.DataFrame


def _map_pandas_dtype(dtype: str) -> str:
    if dtype.startswith("int"):
        return "integer"
    if dtype.startswith("float"):
        return "number"
    if dtype == "bool":
        return "boolean"
    if dtype.startswith("datetime"):
        return "datetime"
    return "string"


def infer_tabular_schema(data: bytes, filename: str) -> InferredSchema:
    """Detect encoding and infer column schema from CSV, TSV, JSON, or JSONL bytes."""
    if not data:
        raise InvalidFileFormat(message="Uploaded file is empty.", field="file")

    lower_name = filename.lower()
    if lower_name.endswith(".parquet"):
        return _infer_parquet_schema(data)
    if lower_name.endswith(".pdf"):
        return _infer_pdf_schema(data)
    if lower_name.endswith(".xlsx"):
        return _infer_excel_schema(data)
    if lower_name.endswith(".xls"):
        return _infer_legacy_excel_schema(data)
    if lower_name.endswith(".json"):
        return _infer_json_schema(data, lines=False)
    if lower_name.endswith(".jsonl"):
        return _infer_json_schema(data, lines=True)
    if lower_name.endswith(".tsv"):
        sep = "\t"
    elif lower_name.endswith(".csv"):
        sep = ","
    else:
        raise InvalidFileFormat(
            message="Only CSV, TSV, JSON, JSONL, XLS, XLSX, Parquet, and PDF files are supported.",
            field="file",
        )

    detected = chardet.detect(data)
    encoding = detected.get("encoding") or "utf-8"

    try:
        dataframe = pd.read_csv(io.BytesIO(data), encoding=encoding, sep=sep)
    except Exception as exc:
        raise SchemaInferenceError(
            message="Could not parse tabular file.",
            field="file",
        ) from exc

    return _dataframe_to_inferred(dataframe)


def _infer_json_schema(data: bytes, *, lines: bool) -> InferredSchema:
    """Parse JSON array or JSON Lines into a flat tabular dataframe."""
    detected = chardet.detect(data)
    encoding = detected.get("encoding") or "utf-8"
    try:
        dataframe = pd.read_json(io.BytesIO(data), encoding=encoding, lines=lines)
    except ValueError as exc:
        raise SchemaInferenceError(
            message="Could not parse JSON file.",
            field="file",
        ) from exc
    except Exception as exc:
        raise SchemaInferenceError(
            message="Could not parse JSON file.",
            field="file",
        ) from exc

    if isinstance(dataframe.columns, pd.MultiIndex):
        dataframe.columns = ["_".join(str(part) for part in column) for column in dataframe.columns]

    return _dataframe_to_inferred(dataframe)


def _infer_parquet_schema(data: bytes) -> InferredSchema:
    try:
        dataframe = pd.read_parquet(io.BytesIO(data))
    except Exception as exc:
        raise SchemaInferenceError(
            message="Could not parse Parquet file.",
            field="file",
        ) from exc
    return _dataframe_to_inferred(dataframe)


def _infer_pdf_schema(data: bytes) -> InferredSchema:
    """Extract the first tabular page from a PDF via pdfplumber."""
    import pdfplumber

    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            table: list[list[str | None]] | None = None
            for page in pdf.pages:
                tables = page.extract_tables()
                if tables:
                    table = tables[0]
                    break
    except Exception as exc:
        raise SchemaInferenceError(
            message="Could not parse PDF file.",
            field="file",
        ) from exc

    if not table or len(table) < 2:
        raise SchemaInferenceError(
            message="PDF contains no extractable table.",
            field="file",
        )

    headers = [str(cell or f"column_{index}") for index, cell in enumerate(table[0])]
    rows: list[dict[str, object]] = []
    for raw_row in table[1:]:
        if not raw_row:
            continue
        row = {
            headers[index]: (raw_row[index] if index < len(raw_row) else None)
            for index in range(len(headers))
        }
        rows.append(row)

    if not rows:
        raise SchemaInferenceError(message="PDF table has no data rows.", field="file")

    dataframe = pd.DataFrame(rows)
    return _dataframe_to_inferred(dataframe)


def _infer_excel_schema(data: bytes) -> InferredSchema:
    try:
        dataframe = pd.read_excel(io.BytesIO(data), engine="openpyxl")
    except Exception as exc:
        raise SchemaInferenceError(
            message="Could not parse Excel file.",
            field="file",
        ) from exc
    return _dataframe_to_inferred(dataframe)


def _infer_legacy_excel_schema(data: bytes) -> InferredSchema:
    """Parse Excel 97–2003 (.xls) workbooks via xlrd."""
    try:
        dataframe = pd.read_excel(io.BytesIO(data), engine="xlrd")
    except Exception as exc:
        raise SchemaInferenceError(
            message="Could not parse legacy Excel (.xls) file.",
            field="file",
        ) from exc
    return _dataframe_to_inferred(dataframe)


def _dataframe_to_inferred(dataframe: pd.DataFrame) -> InferredSchema:
    if dataframe.empty and len(dataframe.columns) == 0:
        raise SchemaInferenceError(message="File contains no columns.", field="file")

    columns = [
        {
            "name": str(column),
            "type": _map_pandas_dtype(str(dataframe[column].dtype)),
            "nullable": bool(dataframe[column].isna().any()),
        }
        for column in dataframe.columns
    ]

    return InferredSchema(
        schema_snapshot={"columns": columns},
        row_count=len(dataframe),
        dataframe=dataframe,
    )
