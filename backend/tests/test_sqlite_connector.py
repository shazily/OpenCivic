"""SQLite connector tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.connectors.sqlite import SqliteConnector


@pytest.mark.asyncio
async def test_sqlite_connector_schema() -> None:
    connector = SqliteConnector(
        {
            "path": "/data/sample.db",
            "table": "datasets",
        }
    )
    rows = [{"id": 1, "title": "Test"}]
    mock_cursor = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=rows)
    mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
    mock_cursor.__aexit__ = AsyncMock(return_value=False)
    mock_conn = MagicMock()
    mock_conn.execute.return_value = mock_cursor
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    mock_aiosqlite = MagicMock()
    mock_aiosqlite.connect = MagicMock(return_value=mock_conn)
    mock_aiosqlite.Row = dict

    with patch.dict("sys.modules", {"aiosqlite": mock_aiosqlite}):
        schema = await connector.get_schema()

    assert schema.row_count == 1
    assert schema.columns[0]["name"] == "id"


@pytest.mark.asyncio
async def test_sqlite_connector_registered() -> None:
    from app.services.connectors.registry import get_connector, registered_types
    from app.services.connectors.sqlite import SqliteConnector as Sqlite

    assert "sqlite" in registered_types()
    connector = get_connector(
        "sqlite",
        {
            "path": "/tmp/test.db",
            "table": "items",
        },
    )
    assert isinstance(connector, Sqlite)
