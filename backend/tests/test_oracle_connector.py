"""Oracle connector tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.connectors.oracle import OracleConnector


@pytest.mark.asyncio
async def test_oracle_connector_schema() -> None:
    connector = OracleConnector(
        {
            "host": "oracle",
            "port": 1521,
            "service_name": "ORCLPDB1",
            "user": "opencivic",
            "password": "secret",
            "table": "DATASETS",
        }
    )
    mock_cursor = AsyncMock()
    mock_cursor.description = [("ID",), ("TITLE",)]
    mock_cursor.fetchall = AsyncMock(return_value=[(1, "Test")])
    mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
    mock_cursor.__aexit__ = AsyncMock(return_value=False)
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.close = AsyncMock()

    mock_oracledb = MagicMock()
    mock_oracledb.makedsn = MagicMock(return_value="oracle-dsn")
    mock_oracledb.connect_async = AsyncMock(return_value=mock_conn)

    with patch.dict("sys.modules", {"oracledb": mock_oracledb}):
        schema = await connector.get_schema()

    assert schema.row_count == 1
    assert schema.columns[0]["name"] == "ID"


@pytest.mark.asyncio
async def test_oracle_connector_registered() -> None:
    from app.services.connectors.oracle import OracleConnector as Oracle
    from app.services.connectors.registry import get_connector, registered_types

    assert "oracle" in registered_types()
    connector = get_connector(
        "oracle",
        {
            "host": "localhost",
            "service_name": "ORCL",
            "user": "u",
            "password": "p",
            "table": "T",
        },
    )
    assert isinstance(connector, Oracle)
