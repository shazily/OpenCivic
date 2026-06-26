"""OpenCivic — Master API v1 router. All endpoints registered here."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    analytics,
    api_keys,
    auth,
    connectors,
    datasets,
    feedback,
    health,
    internal,
    notifications,
    portal,
    scim,
    search,
    users,
    webhooks,
    workflow,
)

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(datasets.router, prefix="/datasets", tags=["datasets"])
api_router.include_router(connectors.router, prefix="/connectors", tags=["connectors"])
api_router.include_router(workflow.router, prefix="/workflow", tags=["workflow"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(scim.router, prefix="/scim", tags=["scim"])
api_router.include_router(api_keys.router, prefix="/api-keys", tags=["api-keys"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(feedback.router, prefix="/feedback", tags=["feedback"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(portal.router, prefix="/portal", tags=["portal"])
api_router.include_router(internal.router, prefix="/internal", tags=["internal"])
