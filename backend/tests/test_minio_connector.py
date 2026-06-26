"""Minio/S3 connector tests."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.connectors.minio_s3 import MinioS3Connector


@pytest.mark.asyncio
async def test_minio_connector_parses_csv() -> None:
    connector = MinioS3Connector(
        {
            "endpoint_url": "http://minio:9000",
            "access_key": "minioadmin",
            "secret_key": "minioadmin",
            "bucket": "opencivic",
            "prefix": "imports/",
        }
    )
    csv_bytes = b"region,population\nNorth,100\nSouth,200\n"

    with patch.object(connector, "_list_keys", new_callable=AsyncMock, return_value=["imports/data.csv"]):
        with patch.object(connector, "_get_object", new_callable=AsyncMock, return_value=csv_bytes):
            schema = await connector.get_schema()

    assert schema.row_count == 2
    assert schema.columns[0]["name"] == "region"


@pytest.mark.asyncio
async def test_minio_connector_registered() -> None:
    from app.services.connectors.registry import get_connector, registered_types

    assert "minio" in registered_types()
    assert "s3" in registered_types()
    connector = get_connector(
        "minio",
        {
            "endpoint_url": "http://minio:9000",
            "access_key": "x",
            "secret_key": "y",
            "bucket": "b",
        },
    )
    assert isinstance(connector, MinioS3Connector)
