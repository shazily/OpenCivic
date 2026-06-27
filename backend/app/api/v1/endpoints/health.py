"""Health check endpoints."""

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.api.v1.dependencies.permissions import AdminRequired
from app.core.cache import verify_cache_connection
from app.core.config import settings
from app.db.session import verify_db_connection
from app.services.storage.storage_client import get_storage_client

router = APIRouter()


@router.get("/live")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def readiness() -> JSONResponse:
    checks: dict[str, str] = {}
    status_code = 200
    try:
        await verify_db_connection()
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
        status_code = 503
    try:
        await verify_cache_connection()
        checks["cache"] = "ok"
    except Exception:
        checks["cache"] = "error"
        status_code = 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ok" if status_code == 200 else "degraded", "checks": checks},
    )


@router.get("/deep")
async def deep_health(current_user: AdminRequired) -> dict:
    """Full system status for IT admin console (not public)."""
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
    try:
        storage = get_storage_client()
        await storage.ensure_bucket(settings.MINIO_BUCKET)
        checks["object_storage"] = "ok"
    except Exception:
        checks["object_storage"] = "error"

    try:
        from app.services.search.qdrant_service import verify_qdrant_connection

        await verify_qdrant_connection()
        checks["qdrant"] = "ok"
    except Exception:
        checks["qdrant"] = "unavailable"

    if settings.LLM_PROVIDER == "ollama" and settings.ai_enabled:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{settings.LLM_BASE_URL}/api/tags")
            checks["ollama"] = "ok" if response.status_code == 200 else "error"
        except Exception:
            checks["ollama"] = "unavailable"

    degraded = any(value not in {"ok", "unavailable"} for value in checks.values())
    return {
        "status": "degraded" if degraded else "ok",
        "version": settings.VERSION,
        "deployment_mode": settings.DEPLOYMENT_MODE,
        "ai_mode": settings.AI_MODE,
        "checks": checks,
    }
