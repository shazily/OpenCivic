"""Idempotent dev seed — platform tenant, publisher user, default licence, Minio bucket."""
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.models import Licence, Tenant, User
from app.db.session import set_tenant_context
from app.services.platform.plan_seed_service import ensure_default_plans
from app.services.platform.tenant_rate_limit_service import hydrate_tenant_rate_limit
from app.services.storage.storage_client import get_storage_client

logger = structlog.get_logger(__name__)

DEV_TENANT_ID = uuid.UUID(settings.DEV_TENANT_ID)
DEV_USER_ID = uuid.UUID(settings.DEV_USER_ID)
DEV_LICENCE_ID = uuid.UUID(settings.DEV_LICENCE_ID)
DEV_STEWARD_USER_ID = uuid.UUID(settings.DEV_STEWARD_USER_ID)
DEV_ADMIN_USER_ID = uuid.UUID(settings.DEV_ADMIN_USER_ID)
DEV_DEVELOPER_USER_ID = uuid.UUID(settings.DEV_DEVELOPER_USER_ID)


async def ensure_minio_bucket() -> None:
    """Create the default object storage bucket if it does not exist."""
    client = get_storage_client()
    bucket = settings.MINIO_BUCKET
    try:
        await client.ensure_bucket(bucket)
        logger.info("minio_bucket_ready", bucket=bucket)
    except Exception as exc:
        logger.warning("minio_bucket_setup_skipped", bucket=bucket, error=str(exc))


async def seed() -> None:
    engine = create_async_engine(settings.DATABASE_WRITE_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        await ensure_default_plans(session)

        existing_tenant = await session.scalar(
            select(Tenant).where(Tenant.id == DEV_TENANT_ID)
        )
        if existing_tenant is None:
            session.add(
                Tenant(
                    id=DEV_TENANT_ID,
                    slug="dev",
                    display_name="OpenCivic Dev Tenant",
                    tier="standard",
                    status="active",
                )
            )
            logger.info("seed_tenant_created", tenant_id=str(DEV_TENANT_ID))

        await set_tenant_context(session, DEV_TENANT_ID)

        existing_user = await session.scalar(select(User).where(User.id == DEV_USER_ID))
        if existing_user is None:
            session.add(
                User(
                    id=DEV_USER_ID,
                    tenant_id=DEV_TENANT_ID,
                    keycloak_user_id="dev-publisher",
                    email="publisher@opencivic.local",
                    name="Dev Publisher",
                    roles=["data_publisher"],
                )
            )
            logger.info("seed_user_created", user_id=str(DEV_USER_ID))

        existing_steward = await session.scalar(
            select(User).where(User.id == DEV_STEWARD_USER_ID)
        )
        if existing_steward is None:
            session.add(
                User(
                    id=DEV_STEWARD_USER_ID,
                    tenant_id=DEV_TENANT_ID,
                    keycloak_user_id="dev-steward",
                    email="steward@opencivic.local",
                    name="Dev Steward",
                    roles=["data_steward"],
                )
            )
            logger.info("seed_steward_created", user_id=str(DEV_STEWARD_USER_ID))

        for user_id, keycloak_id, email, name, roles in (
            (
                DEV_ADMIN_USER_ID,
                "dev-admin",
                "admin@opencivic.local",
                "Dev Org Admin",
                ["org_admin"],
            ),
            (
                DEV_DEVELOPER_USER_ID,
                "dev-developer",
                "developer@opencivic.local",
                "Dev Developer",
                ["developer"],
            ),
        ):
            existing = await session.scalar(select(User).where(User.id == user_id))
            if existing is None:
                session.add(
                    User(
                        id=user_id,
                        tenant_id=DEV_TENANT_ID,
                        keycloak_user_id=keycloak_id,
                        email=email,
                        name=name,
                        roles=roles,
                    )
                )
                logger.info("seed_user_created", user_id=str(user_id))

        existing_licence = await session.scalar(
            select(Licence).where(Licence.id == DEV_LICENCE_ID)
        )
        if existing_licence is None:
            session.add(
                Licence(
                    id=DEV_LICENCE_ID,
                    tenant_id=DEV_TENANT_ID,
                    name="Open Government Licence",
                    url="https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/",
                    spdx_id="OGL-UK-3.0",
                )
            )
            logger.info("seed_licence_created", licence_id=str(DEV_LICENCE_ID))

        await hydrate_tenant_rate_limit(session, DEV_TENANT_ID, tier="standard")
        await session.commit()

    await engine.dispose()
    await ensure_minio_bucket()
    logger.info("seed_complete")


if __name__ == "__main__":
    asyncio.run(seed())
