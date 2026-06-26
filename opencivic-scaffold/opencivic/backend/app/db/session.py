"""
DB session — async, read/write routing, tenant context injection.
RULE: Every transaction sets SET LOCAL app.tenant_id before any query.
RULE: tenant_id always from validated JWT — never from client input.
"""
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated
import structlog
from fastapi import Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.errors import DatabaseError

logger = structlog.get_logger(__name__)

def _make_engine(url: str, app_name: str):
    from app.core.config import settings
    return create_async_engine(
        url, pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_pre_ping=True, echo=False,
        connect_args={"server_settings": {"application_name": app_name}},
    )

def _get_engines():
    from app.core.config import settings
    return (
        _make_engine(settings.DATABASE_WRITE_URL, "opencivic-write"),
        _make_engine(settings.DATABASE_READ_URL, "opencivic-read"),
    )

engine, read_engine = _get_engines()
AsyncWriteSession = async_sessionmaker(bind=engine, class_=AsyncSession, autocommit=False, autoflush=False, expire_on_commit=False)
AsyncReadSession = async_sessionmaker(bind=read_engine, class_=AsyncSession, autocommit=False, autoflush=False, expire_on_commit=False)

async def set_tenant_context(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    """RULE: Called before every query. tenant_id from JWT only — never client input."""
    await session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})
    await session.execute(text("SET LOCAL search_path = :schema, public"), {"schema": f"tenant_{tenant_id.hex}"})

async def get_write_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    tenant_id = getattr(request.state, "tenant_id", None)
    if tenant_id is None:
        raise DatabaseError(code="MISSING_TENANT_CONTEXT", message="No tenant context.")
    async with AsyncWriteSession() as session:
        try:
            await set_tenant_context(session, tenant_id)
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def get_read_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    tenant_id = getattr(request.state, "tenant_id", None)
    async with AsyncReadSession() as session:
        try:
            if tenant_id:
                await set_tenant_context(session, tenant_id)
            yield session
        finally:
            await session.close()

async def verify_db_connection() -> None:
    try:
        async with engine.connect() as c:
            await c.execute(text("SELECT 1"))
        logger.info("database_connection_verified")
    except Exception as e:
        raise DatabaseError(code="DB_CONNECTION_FAILED", message=str(e)) from e

WriteSession = Annotated[AsyncSession, Depends(get_write_session)]
ReadSession = Annotated[AsyncSession, Depends(get_read_session)]
