"""DuckDB sandbox SQL validation tests."""

import pytest

from app.core.errors import ValidationError
from app.services.data.duckdb_sandbox import validate_select_sql


def test_validate_select_allows_simple_query() -> None:
    sql = validate_select_sql("SELECT region, COUNT(*) FROM data GROUP BY region")
    assert sql.startswith("SELECT")


def test_validate_select_rejects_insert() -> None:
    with pytest.raises(ValidationError):
        validate_select_sql("INSERT INTO data VALUES (1)")


def test_validate_select_rejects_multiple_statements() -> None:
    with pytest.raises(ValidationError):
        validate_select_sql("SELECT 1; DROP TABLE data")
