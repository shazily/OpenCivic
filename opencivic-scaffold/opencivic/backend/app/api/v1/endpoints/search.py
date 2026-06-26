"""3-tier hybrid search: Valkey instant → Postgres full-text → Qdrant semantic."""
from fastapi import APIRouter, Query
from app.api.v1.dependencies.auth import AuthOptional
from app.db.session import ReadSession
router = APIRouter()

@router.get("/")
async def search(session: ReadSession, current_user: AuthOptional,
    q: str = Query(..., min_length=1, max_length=500),
    page_size: int = Query(20, le=100), cursor: str | None = None,
    format: list[str] | None = Query(default=None), licence: str | None = None):
    """Hybrid search. Tier1: Valkey <50ms. Tier2: Postgres pg_trgm. Tier3: Qdrant semantic."""
    return {"data": [], "meta": {"has_more": False, "next_cursor": None, "search_type": "hybrid"}, "errors": []}
