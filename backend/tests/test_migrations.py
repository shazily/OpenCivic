"""Migration smoke tests."""
import pytest
from sqlalchemy import inspect


@pytest.mark.asyncio
async def test_core_tables_exist() -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.core.config import settings

    engine = create_async_engine(settings.DATABASE_WRITE_URL, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            table_names = await connection.run_sync(
                lambda sync_conn: inspect(sync_conn).get_table_names(schema="public")
            )
            platform_tables = await connection.run_sync(
                lambda sync_conn: inspect(sync_conn).get_table_names(schema="platform")
            )
    finally:
        await engine.dispose()

    for table in (
        "users",
        "licences",
        "datasets",
        "events",
        "dataset_versions",
        "workflow_submissions",
        "connectors",
        "lineage_nodes",
        "lineage_edges",
    ):
        assert table in table_names
    for table in ("tenants", "audit_log", "plans", "super_admins"):
        assert table in platform_tables
