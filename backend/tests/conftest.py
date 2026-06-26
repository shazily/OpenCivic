"""Pytest fixtures — migrations, seed data, HTTP client."""
import asyncio
import os
import subprocess
import sys
import uuid
from collections.abc import AsyncGenerator, Iterator
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("SECRET_KEY", "testsecretkey32charsminimumhere1")
os.environ.setdefault("DEV_AUTH_ENABLED", "true")
os.environ.setdefault("DEV_AUTH_TOKEN", "test-dev-token")
os.environ.setdefault("DEV_TENANT_ID", "00000000-0000-0000-0000-000000000001")
os.environ.setdefault("DEV_USER_ID", "00000000-0000-0000-0000-000000000002")
os.environ.setdefault("DEV_LICENCE_ID", "00000000-0000-0000-0000-000000000003")
os.environ.setdefault("DEV_STEWARD_USER_ID", "00000000-0000-0000-0000-000000000010")
os.environ.setdefault("DEV_STEWARD_AUTH_TOKEN", "test-steward-token")
os.environ.setdefault("DEV_ADMIN_USER_ID", "00000000-0000-0000-0000-000000000011")
os.environ.setdefault("DEV_ADMIN_AUTH_TOKEN", "test-admin-token")
os.environ.setdefault("DEV_DEVELOPER_USER_ID", "00000000-0000-0000-0000-000000000012")
os.environ.setdefault("DEV_DEVELOPER_AUTH_TOKEN", "test-developer-token")
os.environ.setdefault("SCIM_WEBHOOK_SECRET", "dev-scim-secret-change-me")
os.environ.setdefault("EDGE_RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("GATEWAY_RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("AI_MODE", "disabled")
os.environ.setdefault("DEPLOYMENT_MODE", "selfhosted")
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
os.environ["CLAMAV_ENABLED"] = "false"
os.environ.setdefault("DATABASE_POOL_SIZE", "2")
os.environ.setdefault("DATABASE_MAX_OVERFLOW", "0")
os.environ.setdefault("GATEWAY_AUTH_SECRET", "test-gateway-secret")
os.environ.setdefault("EDGE_AUTH_ENABLED", "false")
os.environ.setdefault("MINIO_ENDPOINT", "http://localhost:9000")
os.environ.setdefault("MINIO_ACCESS_KEY", "minioadmin")
os.environ.setdefault("MINIO_SECRET_KEY", "minioadmin")
os.environ.setdefault("MINIO_BUCKET", "opencivic-test")
_valkey_password = os.environ.get("VALKEY_PASSWORD", "")
if _valkey_password:
    os.environ.setdefault(
        "VALKEY_URL",
        f"redis://:{_valkey_password}@valkey:6379/0",
    )
else:
    os.environ.setdefault("VALKEY_URL", "redis://localhost:6379/0")

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


def _run_migrations() -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = env.get(
        "DATABASE_MIGRATION_URL",
        env.get(
            "DATABASE_WRITE_URL",
            env.get(
                "DATABASE_URL",
                "postgresql+asyncpg://opencivic:password@postgres:5432/opencivic",
            ),
        ),
    )
    env.setdefault("POSTGRES_PASSWORD", "password")
    subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=BACKEND_ROOT,
        check=True,
        env=env,
    )


@pytest.fixture(scope="session")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    """Single event loop for the whole test session (async SQLAlchemy pools)."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def apply_migrations() -> None:
    from app.core.config import get_settings

    get_settings.cache_clear()
    _run_migrations()


@pytest.fixture(scope="session")
def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {os.environ['DEV_AUTH_TOKEN']}"}


@pytest.fixture(scope="session")
def admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {os.environ['DEV_ADMIN_AUTH_TOKEN']}"}


@pytest.fixture(scope="session")
def test_engine():
    from app.core.config import settings

    engine = create_async_engine(
        settings.DATABASE_WRITE_URL,
        pool_pre_ping=True,
        poolclass=NullPool,
    )
    yield engine


@pytest.fixture(scope="session", autouse=True)
def dispose_test_engine(test_engine, event_loop) -> Iterator[None]:
    yield
    event_loop.run_until_complete(test_engine.dispose())


@pytest.fixture(scope="session", autouse=True)
def seed_dev_tenant(test_engine, event_loop) -> None:
    """Seed platform/tenant rows once per session."""
    from app.db.models import Licence, Tenant, User
    from app.db.session import set_tenant_context

    async def _seed() -> None:
        factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
        tenant_id = uuid.UUID(os.environ["DEV_TENANT_ID"])
        user_id = uuid.UUID(os.environ["DEV_USER_ID"])
        licence_id = uuid.UUID(os.environ["DEV_LICENCE_ID"])
        async with factory() as session:
            existing = await session.scalar(select(Tenant).where(Tenant.id == tenant_id))
            if existing is None:
                session.add(
                    Tenant(
                        id=tenant_id,
                        slug="dev",
                        display_name="Test Tenant",
                        tier="standard",
                        status="active",
                    )
                )
            await set_tenant_context(session, tenant_id)
            existing_user = await session.scalar(select(User).where(User.id == user_id))
            if existing_user is None:
                session.add(
                    User(
                        id=user_id,
                        tenant_id=tenant_id,
                        keycloak_user_id="test-publisher",
                        email="publisher@test.local",
                        name="Test Publisher",
                        roles=["data_publisher"],
                    )
                )
            for extra_id, email, roles in (
                (uuid.UUID(os.environ["DEV_STEWARD_USER_ID"]), "steward@test.local", ["data_steward"]),
                (uuid.UUID(os.environ["DEV_ADMIN_USER_ID"]), "admin@test.local", ["org_admin"]),
                (uuid.UUID(os.environ["DEV_DEVELOPER_USER_ID"]), "developer@test.local", ["developer"]),
            ):
                existing_extra = await session.scalar(select(User).where(User.id == extra_id))
                if existing_extra is None:
                    session.add(
                        User(
                            id=extra_id,
                            tenant_id=tenant_id,
                            keycloak_user_id=f"test-{extra_id.hex[:8]}",
                            email=email,
                            name=email.split("@")[0],
                            roles=roles,
                        )
                    )
            existing_licence = await session.scalar(select(Licence).where(Licence.id == licence_id))
            if existing_licence is None:
                session.add(
                    Licence(
                        id=licence_id,
                        tenant_id=tenant_id,
                        name="Test Licence",
                    )
                )
            await session.commit()

    event_loop.run_until_complete(_seed())


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    from app.core.cache import reset_cache_client
    from app.core.config import get_settings
    from app.main import app

    get_settings.cache_clear()
    reset_cache_client()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client


@pytest.fixture(scope="session", autouse=True)
def dispose_app_engines_at_end(event_loop) -> Iterator[None]:
    """Dispose FastAPI SQLAlchemy engines once per session (not per test)."""
    yield

    async def _dispose() -> None:
        from app.db.session import reset_engines

        await reset_engines()

    event_loop.run_until_complete(_dispose())


@pytest.fixture
async def other_tenant_dataset(db_session: AsyncSession) -> uuid.UUID:
    """Dataset row owned by a different tenant for RLS isolation tests."""
    from app.db.models import Dataset, Tenant, User

    other_tenant_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    dataset_id = uuid.uuid4()

    db_session.add(
        Tenant(
            id=other_tenant_id,
            slug=f"other-{other_tenant_id.hex[:8]}",
            display_name="Other Tenant",
            tier="standard",
            status="active",
        )
    )
    await db_session.flush()
    from app.db.session import set_tenant_context

    await set_tenant_context(db_session, other_tenant_id)
    db_session.add(
        User(
            id=other_user_id,
            tenant_id=other_tenant_id,
            keycloak_user_id=f"other-{other_user_id.hex[:8]}",
            email="other@test.local",
            name="Other Publisher",
            roles=["data_publisher"],
        )
    )
    await db_session.flush()
    db_session.add(
        Dataset(
            id=dataset_id,
            tenant_id=other_tenant_id,
            title="Other tenant dataset",
            slug=f"other-{dataset_id.hex[:8]}",
            publisher_id=other_user_id,
            status="draft",
        )
    )
    await db_session.commit()
    return dataset_id
