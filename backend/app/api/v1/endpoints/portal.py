"""Public portal endpoints — branding and tenant-facing metadata."""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from sqlalchemy import select

from app.core.config import settings
from app.db.models import Tenant
from app.db.session import ReadSession

router = APIRouter()

_BRANDING_KEYS = (
    "primary_color",
    "primary_hover_color",
    "accent_color",
    "logo_url",
    "display_name",
)


@router.get("/branding")
async def portal_branding(session: ReadSession) -> dict[str, object]:
    """
    Return white-label design tokens for the active tenant.
    Colours are applied client-side via CSS custom properties.
    """
    tenant_id = uuid.UUID(settings.DEV_TENANT_ID)
    tenant = await session.scalar(select(Tenant).where(Tenant.id == tenant_id))
    config = (tenant.config if tenant else {}) or {}
    branding = {key: config[key] for key in _BRANDING_KEYS if key in config}
    return {
        "data": {
            "tenant_id": str(tenant_id),
            "slug": tenant.slug if tenant else "default",
            "display_name": branding.get("display_name") or (tenant.display_name if tenant else "OpenCivic"),
            "branding": branding,
        },
        "meta": {},
        "errors": [],
    }


@router.get("/capabilities")
async def portal_capabilities() -> dict[str, object]:
    """Public capability flags for portal UI (semantic search degradation banner)."""
    from app.services.search.qdrant_service import is_semantic_search_available

    semantic_available = await is_semantic_search_available()
    return {
        "data": {
            "semantic_search_available": semantic_available,
            "semantic_search_degraded": not semantic_available,
        },
        "meta": {},
        "errors": [],
    }
