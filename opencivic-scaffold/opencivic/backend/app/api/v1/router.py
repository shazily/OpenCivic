"""OpenCivic — Master API v1 router. All endpoints registered here."""
from fastapi import APIRouter
from app.api.v1.endpoints import (
    health, datasets, connectors, workflow,
    search, users, api_keys, webhooks,
    feedback, analytics, admin,
)

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(datasets.router, prefix="/datasets", tags=["datasets"])
api_router.include_router(connectors.router, prefix="/connectors", tags=["connectors"])
api_router.include_router(workflow.router, prefix="/workflow", tags=["workflow"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(api_keys.router, prefix="/api-keys", tags=["api-keys"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(feedback.router, prefix="/feedback", tags=["feedback"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
