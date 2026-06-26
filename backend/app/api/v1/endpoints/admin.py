"""IT admin console API."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.v1.dependencies.permissions import AdminRequired
from app.core.cache import verify_cache_connection
from app.core.config import settings
from app.db.models import Event, Tenant
from app.db.session import ReadSession, WriteSession, verify_db_connection
from app.repositories.connector_repository import ConnectorRepository
from app.schemas.branding import BrandingResponse, BrandingUpdate
from app.schemas.tenant import TenantCreateRequest, TenantResponse
from app.services.events.event_publisher import EventPublisher
from app.services.platform.backup_status import get_backup_status
from app.services.platform.tenant_provisioning_service import TenantProvisioningService

router = APIRouter()

SECURITY_EVENT_TYPES = (
    "DatasetRejected",
    "DatasetChangesRequested",
    "DatasetSubmitted",
    "DatasetPublished",
    "DatasetArchived",
    "DatasetScheduled",
)


@router.get("/overview")
async def admin_overview(
    session: ReadSession,
    current_user: AdminRequired,
) -> dict:
    """Infrastructure and connector summary for the IT admin dashboard."""
    checks: dict[str, str] = {}
    try:
        await verify_db_connection()
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
    try:
        await verify_cache_connection()
        checks["cache"] = "ok"
    except Exception:
        checks["cache"] = "error"

    connectors = await ConnectorRepository(session).list_all()
    backup = await get_backup_status()
    since = datetime.now(UTC) - timedelta(days=7)
    security_count = await session.scalar(
        select(func.count())
        .select_from(Event)
        .where(Event.created_at >= since)
        .where(Event.event_type.in_(SECURITY_EVENT_TYPES))
    )
    connector_matrix = [
        {
            "id": str(item.id),
            "name": item.name,
            "type": item.type,
            "status": item.status,
            "circuit_state": item.circuit_state,
            "failure_count": item.failure_count,
            "last_sync_at": item.last_sync_at.isoformat() if item.last_sync_at else None,
        }
        for item in connectors
    ]
    return {
        "data": {
            "health": checks,
            "deployment_mode": settings.DEPLOYMENT_MODE,
            "version": settings.VERSION,
            "connectors": connector_matrix,
            "backup_status": backup["status"],
            "backup_verified_at": backup.get("verified_at"),
            "backup_message": backup.get("message"),
            "security_events_count": int(security_count or 0),
        },
        "meta": {},
        "errors": [],
    }


_BRANDING_KEYS = (
    "primary_color",
    "primary_hover_color",
    "accent_color",
    "logo_url",
    "display_name",
)


def _branding_from_tenant(tenant: Tenant) -> BrandingResponse:
    config = tenant.config or {}
    branding = {key: str(config[key]) for key in _BRANDING_KEYS if key in config}
    display_name = branding.get("display_name") or tenant.display_name
    return BrandingResponse(
        tenant_id=str(tenant.id),
        slug=tenant.slug,
        display_name=display_name,
        branding=branding,
    )


@router.get("/branding")
async def get_admin_branding(
    session: ReadSession,
    current_user: AdminRequired,
) -> dict:
    """Return white-label branding for the active tenant."""
    tenant = await session.get(Tenant, current_user.tenant_id)
    if tenant is None:
        from app.core.errors import NotFound

        raise NotFound(message="Tenant not found")
    payload = _branding_from_tenant(tenant)
    return {"data": payload.model_dump(), "meta": {}, "errors": []}


@router.patch("/branding")
async def patch_admin_branding(
    body: BrandingUpdate,
    session: WriteSession,
    current_user: AdminRequired,
) -> dict:
    """Update tenant white-label branding (merged into tenant.config)."""
    tenant = await session.get(Tenant, current_user.tenant_id)
    if tenant is None:
        from app.core.errors import NotFound

        raise NotFound(message="Tenant not found")

    config = dict(tenant.config or {})
    updates = body.model_dump(exclude_none=True)
    config.update(updates)
    tenant.config = config
    if body.display_name is not None:
        tenant.display_name = body.display_name
    await session.flush()

    await EventPublisher.publish(
        session,
        tenant_id=current_user.tenant_id,
        event_type="TenantBrandingUpdated",
        aggregate_id=tenant.id,
        aggregate_type="tenant",
        actor_id=current_user.user_id,
        payload={"keys": list(updates.keys())},
    )
    await session.commit()

    payload = _branding_from_tenant(tenant)
    return {"data": payload.model_dump(), "meta": {}, "errors": []}


@router.post("/tenants", status_code=201)
async def create_tenant(
    body: TenantCreateRequest,
    session: WriteSession,
    current_user: AdminRequired,
) -> dict:
    """Provision a new tenant (standard tier uses shared schema + RLS)."""
    del current_user
    tenant = await TenantProvisioningService().provision(
        session,
        slug=body.slug,
        display_name=body.display_name,
        tier=body.tier,
    )
    await session.commit()
    payload = TenantResponse(
        id=str(tenant.id),
        slug=tenant.slug,
        display_name=tenant.display_name,
        tier=tenant.tier,
        status=tenant.status,
    )
    return {"data": payload.model_dump(), "meta": {}, "errors": []}


@router.get("/backup/status")
async def backup_status(current_user: AdminRequired) -> dict:
    """Last backup verification snapshot for the IT admin console."""
    del current_user
    backup = await get_backup_status()
    return {
        "data": backup,
        "meta": {},
        "errors": [],
    }


@router.get("/security-events")
async def security_events(
    session: ReadSession,
    current_user: AdminRequired,
    limit: int = Query(50, le=200),
) -> dict:
    """Recent governance and workflow events for the security feed."""
    result = await session.execute(
        select(Event)
        .where(Event.event_type.in_(SECURITY_EVENT_TYPES))
        .order_by(Event.created_at.desc())
        .limit(limit)
    )
    items = result.scalars().all()
    return {
        "data": [
            {
                "id": item.id,
                "event_type": item.event_type,
                "aggregate_id": str(item.aggregate_id),
                "aggregate_type": item.aggregate_type,
                "actor_id": str(item.actor_id) if item.actor_id else None,
                "actor_type": item.actor_type,
                "created_at": item.created_at.isoformat(),
                "payload": item.payload,
            }
            for item in items
        ],
        "meta": {"total_count": len(items)},
        "errors": [],
    }


@router.get("/jobs/summary")
async def admin_jobs_summary(
    current_user: AdminRequired,
) -> dict:
    """Celery queue depths from Valkey broker with optional Flower worker count."""
    from app.services.platform.celery_queue_service import (
        depth_trend_stub,
        get_celery_queue_snapshots,
    )

    snapshots, source, worker_count = await get_celery_queue_snapshots()
    queues = [
        {
            "name": item.name,
            "depth": item.depth,
            "status": item.status,
            "depth_trend": depth_trend_stub(item.depth),
        }
        for item in snapshots
    ]
    total_depth = sum(item.depth for item in snapshots)
    return {
        "data": {
            "queues": queues,
            "source": source,
            "total_depth": total_depth,
            "worker_count": worker_count,
        },
        "meta": {},
        "errors": [],
    }
