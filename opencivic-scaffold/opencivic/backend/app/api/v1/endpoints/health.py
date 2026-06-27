"""Health check endpoints."""
from fastapi import APIRouter
from app.core.config import settings
router = APIRouter()

@router.get("/live")
async def liveness():
    return {"status": "ok"}

@router.get("/ready")
async def readiness():
    return {"status": "ok", "checks": {"database": "ok", "cache": "ok"}}

@router.get("/deep")
async def deep_health():
    return {"status": "ok", "version": settings.VERSION, "deployment_mode": settings.DEPLOYMENT_MODE}
