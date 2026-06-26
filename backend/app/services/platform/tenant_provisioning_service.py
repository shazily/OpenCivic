"""Tenant provisioning — idempotent platform onboarding steps."""

from __future__ import annotations

import re
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import SlugConflict, ValidationError
from app.db.models import Licence, Tenant
from app.db.session import set_tenant_context
from app.services.platform.plan_seed_service import ensure_default_plans
from app.services.platform.tenant_rate_limit_service import hydrate_tenant_rate_limit
from app.services.storage.storage_client import get_storage_client

logger = structlog.get_logger(__name__)

_SLUG_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


class TenantProvisioningService:
    """Create a new tenant record and run first-run setup steps."""

    async def provision(
        self,
        session: AsyncSession,
        *,
        slug: str,
        display_name: str,
        tier: str = "standard",
    ) -> Tenant:
        normalized_slug = slug.strip().lower()
        if not _SLUG_PATTERN.match(normalized_slug):
            raise ValidationError(
                message="Tenant slug must be 1–63 lowercase letters, digits, or hyphens.",
                field="slug",
            )

        existing = await session.scalar(select(Tenant).where(Tenant.slug == normalized_slug))
        if existing is not None:
            raise SlugConflict(message="Tenant slug is already registered.", field="slug")

        await ensure_default_plans(session)

        tenant_id = uuid.uuid4()
        schema_name = f"schema_{normalized_slug}" if tier == "professional" else None
        tenant = Tenant(
            id=tenant_id,
            slug=normalized_slug,
            display_name=display_name.strip(),
            tier=tier,
            schema_name=schema_name,
            status="active",
        )
        session.add(tenant)
        await session.flush()

        await self._seed_default_licence(session, tenant_id)
        await self._ensure_storage_prefix(tenant_id)
        await hydrate_tenant_rate_limit(session, tenant_id, tier=tier)
        logger.info(
            "tenant_provisioned",
            tenant_id=str(tenant_id),
            slug=normalized_slug,
            tier=tier,
        )
        return tenant

    async def _seed_default_licence(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        await set_tenant_context(session, tenant_id)
        existing = await session.scalar(
            select(Licence).where(Licence.tenant_id == tenant_id).limit(1)
        )
        if existing is not None:
            return
        session.add(
            Licence(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                name="Open Government Licence",
                url="https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/",
                spdx_id="OGL-UK-3.0",
            )
        )
        await session.flush()

    async def _ensure_storage_prefix(self, tenant_id: uuid.UUID) -> None:
        from app.core.config import settings

        client = get_storage_client()
        marker_key = f"tenants/{tenant_id}/.keep"
        try:
            await client.ensure_bucket(settings.MINIO_BUCKET)
            await client.put(marker_key, b"", content_type="application/octet-stream")
        except Exception as exc:
            logger.warning("tenant_storage_prefix_skipped", tenant_id=str(tenant_id), error=str(exc))
