"""Seed default platform subscription plans — idempotent."""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Plan

logger = structlog.get_logger(__name__)

DEFAULT_PLANS: tuple[dict[str, object], ...] = (
    {
        "id": uuid.UUID("00000000-0000-0000-0000-000000000101"),
        "name": "Standard",
        "max_datasets": 100,
        "max_users": 50,
        "max_storage_gb": 50,
        "api_rate_limit_per_min": 1000,
        "ai_enabled": True,
        "price_monthly": 0,
    },
    {
        "id": uuid.UUID("00000000-0000-0000-0000-000000000102"),
        "name": "Professional",
        "max_datasets": 500,
        "max_users": 200,
        "max_storage_gb": 250,
        "api_rate_limit_per_min": 2500,
        "ai_enabled": True,
        "price_monthly": 499,
    },
    {
        "id": uuid.UUID("00000000-0000-0000-0000-000000000103"),
        "name": "Enterprise",
        "max_datasets": None,
        "max_users": None,
        "max_storage_gb": None,
        "api_rate_limit_per_min": 5000,
        "ai_enabled": True,
        "price_monthly": None,
    },
)


async def ensure_default_plans(session: AsyncSession) -> int:
    """Insert missing default plans; returns count of plans created."""
    created = 0
    for spec in DEFAULT_PLANS:
        name = str(spec["name"])
        existing = await session.scalar(select(Plan).where(Plan.name == name).limit(1))
        if existing is not None:
            continue
        session.add(
            Plan(
                id=spec["id"],  # type: ignore[arg-type]
                name=name,
                max_datasets=spec.get("max_datasets"),  # type: ignore[arg-type]
                max_users=spec.get("max_users"),  # type: ignore[arg-type]
                max_storage_gb=spec.get("max_storage_gb"),  # type: ignore[arg-type]
                api_rate_limit_per_min=spec.get("api_rate_limit_per_min"),  # type: ignore[arg-type]
                ai_enabled=bool(spec.get("ai_enabled", True)),
                price_monthly=spec.get("price_monthly"),  # type: ignore[arg-type]
            )
        )
        created += 1
    if created:
        await session.flush()
        logger.info("platform_plans_seeded", created=created)
    return created
