"""Analytics API — public dataset usage summaries and developer gauges."""

import uuid

from fastapi import APIRouter, Query

from app.api.v1.dependencies.auth import AuthOptional
from app.api.v1.dependencies.permissions import AdminRequired, DeveloperRequired, PublisherRequired
from app.core.cache import cache_get
from app.db.session import ReadSession, set_tenant_context
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.usage_event_repository import UsageEventRepository
from app.schemas.analytics import DatasetUsageSummary, OrgUsageSummary, PublisherUsageSummary
from app.services.analytics.rate_limit_service import RateLimitService

router = APIRouter()


async def _cached_count(tenant_id: uuid.UUID, dataset_id: uuid.UUID, event_type: str) -> int | None:
    raw = await cache_get(f"usage:{tenant_id}:{dataset_id}:{event_type}")
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


@router.get("/datasets/{dataset_id}/summary")
async def dataset_usage_summary(
    dataset_id: uuid.UUID,
    session: ReadSession,
    current_user: AuthOptional,
) -> dict:
    """Public usage summary for a published dataset."""
    repo = DatasetRepository(session)
    dataset = await repo.get_by_id(dataset_id)
    if dataset.status != "published":
        from app.core.errors import DatasetNotFound

        raise DatasetNotFound(message="Dataset not found.")
    if current_user is None:
        await set_tenant_context(session, dataset.tenant_id)

    usage_repo = UsageEventRepository(session)
    counts = await usage_repo.counts_for_dataset(dataset_id)

    cached_views = await _cached_count(dataset.tenant_id, dataset_id, "view")
    cached_downloads = await _cached_count(dataset.tenant_id, dataset_id, "download")
    cached_api = await _cached_count(dataset.tenant_id, dataset_id, "api_call")

    views = cached_views if cached_views is not None else counts.get("view", 0)
    downloads = cached_downloads if cached_downloads is not None else counts.get("download", 0)
    api_calls = cached_api if cached_api is not None else counts.get("api_call", 0)

    feedback_count, average_rating = await FeedbackRepository(session).summary_for_dataset(
        dataset_id
    )

    summary = DatasetUsageSummary(
        views=views,
        downloads=downloads,
        api_calls=api_calls,
        feedback_count=feedback_count,
        average_rating=average_rating,
    )
    return {
        "data": summary.model_dump(mode="json"),
        "meta": {},
        "errors": [],
    }


@router.get("/datasets/{dataset_id}/trend")
async def dataset_engagement_trend(
    dataset_id: uuid.UUID,
    session: ReadSession,
    current_user: AuthOptional,
    days: int = Query(14, ge=7, le=30),
) -> dict:
    """Daily view/download trend for public dataset sparklines."""
    repo = DatasetRepository(session)
    dataset = await repo.get_by_id(dataset_id)
    if dataset.status != "published":
        from app.core.errors import DatasetNotFound

        raise DatasetNotFound(message="Dataset not found.")
    if current_user is None:
        await set_tenant_context(session, dataset.tenant_id)

    trend = await UsageEventRepository(session).daily_engagement_trend(dataset_id, days=days)
    return {
        "data": trend,
        "meta": {"days": days, "total_count": len(trend)},
        "errors": [],
    }


@router.get("/publisher/summary")
async def publisher_usage_summary(
    session: ReadSession,
    current_user: PublisherRequired,
) -> dict:
    """Usage totals across datasets owned by the authenticated publisher."""
    from sqlalchemy import func, select

    from app.db.models import Dataset

    dataset_count = await session.scalar(
        select(func.count())
        .select_from(Dataset)
        .where(Dataset.publisher_id == current_user.user_id)
    )
    published_count = await session.scalar(
        select(func.count())
        .select_from(Dataset)
        .where(
            Dataset.publisher_id == current_user.user_id,
            Dataset.status == "published",
        )
    )
    totals = await UsageEventRepository(session).publisher_totals(current_user.user_id)
    summary = PublisherUsageSummary(
        dataset_count=int(dataset_count or 0),
        published_count=int(published_count or 0),
        views=totals["views"],
        downloads=totals["downloads"],
        api_calls=totals["api_calls"],
        ai_queries=totals["ai_queries"],
    )
    return {
        "data": summary.model_dump(mode="json"),
        "meta": {},
        "errors": [],
    }


@router.get("/org/summary")
async def org_usage_summary(
    session: ReadSession,
    current_user: AdminRequired,
) -> dict:
    """Tenant-wide usage totals for the org admin console."""
    from sqlalchemy import func, select

    from app.db.models import Dataset, User

    user_count = await session.scalar(select(func.count()).select_from(User))
    dataset_count = await session.scalar(select(func.count()).select_from(Dataset))
    published_count = await session.scalar(
        select(func.count()).select_from(Dataset).where(Dataset.status == "published")
    )
    totals = await UsageEventRepository(session).tenant_totals()
    summary = OrgUsageSummary(
        user_count=int(user_count or 0),
        dataset_count=int(dataset_count or 0),
        published_count=int(published_count or 0),
        views=totals["views"],
        downloads=totals["downloads"],
        api_calls=totals["api_calls"],
        ai_queries=totals["ai_queries"],
    )
    return {
        "data": summary.model_dump(mode="json"),
        "meta": {},
        "errors": [],
    }


@router.get("/request-logs")
async def request_logs(
    session: ReadSession,
    current_user: DeveloperRequired,
    limit: int = Query(50, le=200),
) -> dict:
    """Recent API usage events for the authenticated developer."""
    from sqlalchemy import select

    from app.db.models import UsageEvent

    result = await session.execute(
        select(UsageEvent)
        .where(UsageEvent.event_type == "api_call")
        .order_by(UsageEvent.created_at.desc())
        .limit(limit)
    )
    items = result.scalars().all()
    return {
        "data": [
            {
                "id": item.id,
                "dataset_id": str(item.dataset_id) if item.dataset_id else None,
                "event_type": item.event_type,
                "api_key_id": str(item.api_key_id) if item.api_key_id else None,
                "format": item.format,
                "response_ms": item.response_ms,
                "created_at": item.created_at.isoformat(),
            }
            for item in items
        ],
        "meta": {"total_count": len(items)},
        "errors": [],
    }


@router.get("/rate-limits")
async def rate_limit_gauges(
    session: ReadSession,
    current_user: DeveloperRequired,
) -> dict:
    """Per API key rate limit utilization for the developer console."""
    from app.core.config import settings
    from app.services.auth.edge_rate_limit import get_tenant_rate_limit

    gauges = await RateLimitService(session).gauges_for_owner(current_user.user_id)
    tenant_limit = await get_tenant_rate_limit(current_user.tenant_id)
    return {
        "data": gauges,
        "meta": {
            "total_count": len(gauges),
            "tenant_limit_per_minute": tenant_limit or settings.DEFAULT_API_RATE_LIMIT_PER_MIN,
        },
        "errors": [],
    }
