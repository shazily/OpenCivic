"""MSSQL connector tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.connectors.mssql import MssqlConnector


@pytest.mark.asyncio
async def test_mssql_connector_schema() -> None:
    connector = MssqlConnector(
        {
            "host": "mssql",
            "port": 1433,
            "database": "opencivic",
            "user": "sa",
            "password": "secret",
            "table": "datasets",
        }
    )
    rows = [{"id": 1, "title": "Test"}]
    mock_cursor = AsyncMock()
    mock_cursor.description = [("id",), ("title",)]
    mock_cursor.fetchall = AsyncMock(return_value=[(1, "Test")])
    mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
    mock_cursor.__aexit__ = AsyncMock(return_value=False)
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.close = AsyncMock()

    mock_aioodbc = MagicMock()
    mock_aioodbc.connect = AsyncMock(return_value=mock_conn)

    with patch.dict("sys.modules", {"aioodbc": mock_aioodbc}):
        schema = await connector.get_schema()

    assert schema.row_count == 1
    assert schema.columns[0]["name"] == "id"


@pytest.mark.asyncio
async def test_mssql_connector_registered() -> None:
    from app.services.connectors.mssql import MssqlConnector as Mssql
    from app.services.connectors.registry import get_connector, registered_types

    assert "mssql" in registered_types()
    connector = get_connector(
        "mssql",
        {
            "host": "localhost",
            "database": "db",
            "user": "u",
            "password": "p",
            "table": "t",
        },
    )
    assert isinstance(connector, Mssql)
