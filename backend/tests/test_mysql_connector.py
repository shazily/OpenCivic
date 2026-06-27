"""MySQL connector tests."""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.connectors.mysql import MysqlConnector


@pytest.mark.asyncio
async def test_mysql_connector_schema() -> None:
    connector = MysqlConnector(
        {
            "host": "mysql",
            "port": 3306,
            "database": "opencivic",
            "user": "root",
            "password": "secret",
            "table": "datasets",
        }
    )
    rows = [{"id": 1, "title": "Test"}]
    mock_cursor = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=rows)
    mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
    mock_cursor.__aexit__ = AsyncMock(return_value=False)
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.close = MagicMock()

    mock_aiomysql = MagicMock()
    mock_aiomysql.connect = AsyncMock(return_value=mock_conn)
    mock_aiomysql.DictCursor = object()

    with patch.dict("sys.modules", {"aiomysql": mock_aiomysql}):
        schema = await connector.get_schema()

    assert schema.row_count == 1
    assert schema.columns[0]["name"] == "id"


@pytest.mark.asyncio
async def test_mysql_connector_registered() -> None:
    from app.services.connectors.mysql import MysqlConnector as Mysql
    from app.services.connectors.registry import get_connector, registered_types

    assert "mysql" in registered_types()
    connector = get_connector(
        "mysql",
        {
            "host": "localhost",
            "database": "db",
            "user": "u",
            "password": "p",
            "table": "t",
        },
    )
    assert isinstance(connector, Mysql)
