"""Query ingested Parquet snapshots with pandas."""

import io
from typing import Any

import pandas as pd

from app.core.errors import ValidationError


def _json_safe(value: object) -> object:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def _parse_fields(fields: str | None, allowed: set[str]) -> list[str] | None:
    if not fields:
        return None
    columns = [column.strip() for column in fields.split(",") if column.strip()]
    if not columns:
        return None
    for column in columns:
        if column not in allowed:
            raise ValidationError(
                message=f"Unknown field '{column}'.",
                field="fields",
            )
    return columns


def _parse_sort(sort: str | None, allowed: set[str]) -> tuple[str, bool] | None:
    if not sort:
        return None
    descending = sort.startswith("-")
    column = sort[1:] if descending else sort
    if column not in allowed:
        raise ValidationError(
            message=f"Unknown sort field '{column}'.",
            field="sort",
        )
    return column, descending


def query_parquet_page(
    parquet_bytes: bytes,
    *,
    allowed_columns: set[str],
    page_size: int,
    offset: int,
    fields: str | None = None,
    sort: str | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    """Return a page of rows from Parquet bytes and whether more pages exist."""
    dataframe = pd.read_parquet(io.BytesIO(parquet_bytes))

    selected = _parse_fields(fields, allowed_columns)
    if selected is not None:
        dataframe = dataframe[selected]

    sort_spec = _parse_sort(sort, allowed_columns)
    if sort_spec is not None:
        column, descending = sort_spec
        dataframe = dataframe.sort_values(by=column, ascending=not descending)

    slice_end = offset + page_size + 1
    page_frame = dataframe.iloc[offset:slice_end]
    has_more = len(page_frame) > page_size
    if has_more:
        page_frame = page_frame.iloc[:page_size]

    rows = [
        {str(key): _json_safe(value) for key, value in record.items()}
        for record in page_frame.to_dict(orient="records")
    ]
    return rows, has_more
