"""Connector type registry."""

from __future__ import annotations

from collections.abc import Callable

from app.core.errors import ConnectorNotFound
from app.services.connectors.base import ConnectorBase
from app.services.connectors.minio_s3 import MinioS3Connector
from app.services.connectors.mssql import MssqlConnector
from app.services.connectors.mysql import MysqlConnector
from app.services.connectors.oracle import OracleConnector
from app.services.connectors.postgres import PostgresConnector
from app.services.connectors.rest_api import RestApiConnector
from app.services.connectors.sqlite import SqliteConnector

_REGISTRY: dict[str, Callable[[dict], ConnectorBase]] = {
    "rest_api": RestApiConnector,
    "minio": MinioS3Connector,
    "s3": MinioS3Connector,
    "postgres": PostgresConnector,
    "mysql": MysqlConnector,
    "mssql": MssqlConnector,
    "oracle": OracleConnector,
    "sqlite": SqliteConnector,
}


def get_connector(type_name: str, config: dict) -> ConnectorBase:
    """Instantiate a connector implementation by type string."""
    factory = _REGISTRY.get(type_name)
    if factory is None:
        raise ConnectorNotFound(message=f"Unknown connector type: {type_name}")
    return factory(config)


def registered_types() -> list[str]:
    return sorted(_REGISTRY.keys())
