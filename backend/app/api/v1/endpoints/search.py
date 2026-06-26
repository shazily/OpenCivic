"""3-tier hybrid search: Valkey instant → Postgres full-text → Qdrant semantic."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.v1.dependencies.auth import AuthOptional
from app.api.v1.endpoints.datasets import _dataset_to_response
from app.db.session import ReadSession
from app.schemas.dataset import DatasetListResponse, PaginationMeta
from app.services.search.search_service import SearchService

router = APIRouter()


@router.get("/")
async def search(
    session: ReadSession,
    current_user: AuthOptional,
    q: str = Query(..., min_length=1, max_length=500),
    page_size: int = Query(20, le=100),
    cursor: str | None = None,
    format: Annotated[list[str] | None, Query()] = None,
    licence: str | None = None,
    filter_status: str | None = Query(None, alias="filter[status]"),
    filter_tag: str | None = Query(None, alias="filter[tag]"),
) -> DatasetListResponse:
    """Hybrid search. Tier 2 (Postgres pg_trgm) is active; Valkey and Qdrant degrade gracefully."""
    licence_id = uuid.UUID(licence) if licence else None
    effective_status = filter_status
    if current_user is None:
        effective_status = "published"

    from app.core.config import settings

    tenant_id = current_user.tenant_id if current_user else uuid.UUID(settings.DEV_TENANT_ID)
    if current_user is None:
        from app.db.session import set_tenant_context

        await set_tenant_context(session, tenant_id)

    service = SearchService(session)
    items, has_more, next_cursor, total_count = await service.search_datasets(
        q,
        page_size=page_size,
        cursor=cursor,
        licence_id=licence_id,
        status=effective_status,
        tag=filter_tag,
        tenant_id=tenant_id,
    )

    from app.services.search.qdrant_service import is_semantic_search_available

    semantic_available = await is_semantic_search_available()

    return DatasetListResponse(
        data=[_dataset_to_response(item) for item in items],
        meta=PaginationMeta(
            has_more=has_more,
            next_cursor=next_cursor,
            total_count=total_count,
            semantic_search_degraded=not semantic_available,
        ),
    )


@router.get("/palette")
async def command_palette(
    session: ReadSession,
    current_user: AuthOptional,
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(8, le=20),
) -> dict:
    """Instant Cmd+K palette search — Valkey-cached title/slug lookup."""
    from app.core.config import settings
    from app.db.session import set_tenant_context
    from app.services.search.command_palette_service import CommandPaletteService

    tenant_id = current_user.tenant_id if current_user else uuid.UUID(settings.DEV_TENANT_ID)
    if current_user is None:
        await set_tenant_context(session, tenant_id)

    hits = await CommandPaletteService(session, tenant_id).search(q, limit=limit)
    return {
        "data": hits,
        "meta": {"query": q, "total_count": len(hits)},
        "errors": [],
    }
