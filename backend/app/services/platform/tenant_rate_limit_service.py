"""Hydrate per-tenant API rate limits into Valkey for edge enforcement."""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Plan, Tenant
from app.services.auth.edge_rate_limit import cache_tenant_rate_limit

logger = structlog.get_logger(__name__)

_TIER_DEFAULT_LIMITS: dict[str, int] = {
    "standard": 1000,
    "professional": 2500,
    "enterprise": 5000,
}


def resolve_rate_limit_for_tier(tier: str, plan_limit: int | None = None) -> int:
    """Resolve per-minute API limit from plan override, tier default, or platform default."""
    if plan_limit is not None and plan_limit > 0:
        return plan_limit
    tier_limit = _TIER_DEFAULT_LIMITS.get(tier)
    if tier_limit is not None:
        return tier_limit
    return settings.DEFAULT_API_RATE_LIMIT_PER_MIN


async def hydrate_tenant_rate_limit(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    tier: str,
) -> int:
    """Write tenant rate limit to Valkey; returns the limit applied."""
    plan_limit = await _lookup_plan_limit(session, tier)
    limit = resolve_rate_limit_for_tier(tier, plan_limit)
    await cache_tenant_rate_limit(tenant_id, limit)
    logger.info("tenant_rate_limit_hydrated", tenant_id=str(tenant_id), tier=tier, limit=limit)
    return limit


async def _lookup_plan_limit(session: AsyncSession, tier: str) -> int | None:
    """Match platform plan by tier name when a plan row exists."""
    plan_name = {
        "standard": "Standard",
        "professional": "Professional",
        "enterprise": "Enterprise",
    }.get(tier, "Standard")
    plan = await session.scalar(select(Plan).where(Plan.name == plan_name).limit(1))
    if plan is None:
        return None
    return plan.api_rate_limit_per_min
