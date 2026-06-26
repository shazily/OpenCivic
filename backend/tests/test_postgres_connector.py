"""PostgreSQL connector tests."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.connectors.postgres import PostgresConnector


@pytest.mark.asyncio
async def test_postgres_connector_schema() -> None:
    connector = PostgresConnector(
        {
            "host": "postgres",
            "port": 5432,
            "database": "opencivic",
            "user": "opencivic",
            "password": "secret",
            "table": "datasets",
        }
    )
    record = {"id": "uuid-1", "title": "Test"}

    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = [record]
    mock_conn.close = AsyncMock()

    with patch.object(connector, "_connect", new_callable=AsyncMock, return_value=mock_conn):
        schema = await connector.get_schema()

    assert schema.row_count == 1
    assert schema.columns[0]["name"] == "id"


@pytest.mark.asyncio
async def test_postgres_connector_registered() -> None:
    from app.services.connectors.postgres import PostgresConnector as Pg
    from app.services.connectors.registry import get_connector, registered_types

    assert "postgres" in registered_types()
    connector = get_connector(
        "postgres",
        {
            "host": "localhost",
            "database": "db",
            "user": "u",
            "password": "p",
            "table": "t",
        },
    )
    assert isinstance(connector, Pg)
