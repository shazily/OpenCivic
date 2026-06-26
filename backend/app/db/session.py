"""
DB session — async, read/write routing, tenant context injection.
RULE: Every transaction sets SET LOCAL app.tenant_id before any query.
RULE: tenant_id always from validated JWT — never from client input.
"""

import uuid
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

import structlog
from fastapi import Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.api.v1.dependencies.auth import CurrentUser, get_current_user, get_current_user_optional
from app.core.errors import DatabaseError

logger = structlog.get_logger(__name__)


def _make_engine(url: str, app_name: str):
    from app.core.config import settings

    return create_async_engine(
        url,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_pre_ping=True,
        echo=False,
        connect_args={"server_settings": {"application_name": app_name}},
    )


engine: AsyncEngine | None = None
read_engine: AsyncEngine | None = None
AsyncWriteSession: async_sessionmaker[AsyncSession] | None = None
AsyncReadSession: async_sessionmaker[AsyncSession] | None = None


def _ensure_engines() -> None:
    """Lazy-init engines so pytest can bind them to the active event loop."""
    global engine, read_engine, AsyncWriteSession, AsyncReadSession
    if engine is not None and AsyncWriteSession is not None:
        return
    from app.core.config import settings

    engine = _make_engine(settings.DATABASE_WRITE_URL, "opencivic-write")
    read_engine = _make_engine(settings.DATABASE_READ_URL, "opencivic-read")
    AsyncWriteSession = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )
    AsyncReadSession = async_sessionmaker(
        bind=read_engine,
        class_=AsyncSession,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )


async def reset_engines() -> None:
    """Dispose pooled connections (used between pytest modules)."""
    global engine, read_engine, AsyncWriteSession, AsyncReadSession
    if engine is not None:
        await engine.dispose()
    if read_engine is not None:
        await read_engine.dispose()
    engine = read_engine = None
    AsyncWriteSession = AsyncReadSession = None


async def set_tenant_context(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> None:
    """RULE: Standard tier — shared schema + RLS via app.tenant_id session variable."""
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )
    if user_id is not None:
        await session.execute(
            text("SELECT set_config('app.user_id', :uid, true)"),
            {"uid": str(user_id)},
        )


async def get_write_session(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> AsyncGenerator[AsyncSession, None]:
    tenant_id = current_user.tenant_id
    user_id = current_user.user_id
    if tenant_id is None:
        raise DatabaseError(code="MISSING_TENANT_CONTEXT", message="No tenant context.")
    _ensure_engines()
    async with AsyncWriteSession() as session:
        try:
            await set_tenant_context(session, tenant_id, user_id)
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_read_session(
    request: Request,
    current_user: Annotated[CurrentUser | None, Depends(get_current_user_optional)],
) -> AsyncGenerator[AsyncSession, None]:
    tenant_id = current_user.tenant_id if current_user else None
    user_id = current_user.user_id if current_user else None
    _ensure_engines()
    async with AsyncReadSession() as session:
        try:
            if tenant_id:
                await set_tenant_context(session, tenant_id, user_id)
            yield session
        finally:
            await session.close()


@asynccontextmanager
async def tenant_write_session(tenant_id: uuid.UUID) -> AsyncIterator[AsyncSession]:
    """Write session with tenant RLS context for workers and background jobs."""
    _ensure_engines()
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


async def verify_db_connection() -> None:
    try:
        _ensure_engines()
        async with engine.connect() as c:
            await c.execute(text("SELECT 1"))
        logger.info("database_connection_verified")
    except Exception as e:
        raise DatabaseError(code="DB_CONNECTION_FAILED", message=str(e)) from e


async def get_optional_write_session(
    request: Request,
    current_user: Annotated[CurrentUser | None, Depends(get_current_user_optional)],
) -> AsyncGenerator[AsyncSession, None]:
    """Write session for endpoints that allow anonymous writes after tenant is resolved."""
    tenant_id = current_user.tenant_id if current_user else None
    user_id = current_user.user_id if current_user else None
    _ensure_engines()
    async with AsyncWriteSession() as session:
        try:
            if tenant_id:
                await set_tenant_context(session, tenant_id, user_id)
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


WriteSession = Annotated[AsyncSession, Depends(get_write_session)]
ReadSession = Annotated[AsyncSession, Depends(get_read_session)]
OptionalWriteSession = Annotated[AsyncSession, Depends(get_optional_write_session)]
