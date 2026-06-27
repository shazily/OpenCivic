"""In-app notification endpoints for staff users."""

import asyncio
import json

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.api.v1.dependencies.auth import AuthRequired
from app.core.errors import NotFound
from app.services.notifications.in_app_service import InAppNotificationService

router = APIRouter()

SSE_HEARTBEAT_SECONDS = 15


@router.get("/")
async def list_notifications(
    current_user: AuthRequired,
    limit: int = Query(20, le=50),
) -> dict:
    """Recent in-app notifications for the authenticated user."""
    items = await InAppNotificationService.list_for_user(
        current_user.tenant_id,
        current_user.user_id,
        limit=limit,
    )
    unread = sum(1 for item in items if not item.get("read"))
    return {
        "data": items,
        "meta": {"total_count": len(items), "unread_count": unread},
        "errors": [],
    }


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: AuthRequired,
) -> dict:
    """Mark a single notification as read."""
    found = await InAppNotificationService.mark_read(
        current_user.tenant_id,
        current_user.user_id,
        notification_id,
    )
    if not found:
        raise NotFound(message="Notification not found.")
    return {
        "data": {"read": True, "id": notification_id},
        "meta": {},
        "errors": [],
    }


@router.post("/read-all")
async def mark_all_notifications_read(current_user: AuthRequired) -> dict:
    """Mark all notifications as read for the current user."""
    count = await InAppNotificationService.mark_all_read(
        current_user.tenant_id,
        current_user.user_id,
    )
    return {
        "data": {"marked_read": count},
        "meta": {},
        "errors": [],
    }


@router.get("/unread-count")
async def notification_unread_count(current_user: AuthRequired) -> dict:
    """Unread notification count for header badge."""
    count = await InAppNotificationService.unread_count(
        current_user.tenant_id,
        current_user.user_id,
    )
    return {
        "data": {"unread_count": count},
        "meta": {},
        "errors": [],
    }


@router.get("/stream")
async def notification_stream(current_user: AuthRequired) -> StreamingResponse:
    """SSE stream with periodic heartbeats for live notification badge refresh."""

    async def event_generator():
        yield f"event: connected\ndata: {json.dumps({'user_id': str(current_user.user_id)})}\n\n"
        while True:
            count = await InAppNotificationService.unread_count(
                current_user.tenant_id,
                current_user.user_id,
            )
            yield f"event: heartbeat\ndata: {json.dumps({'unread_count': count})}\n\n"
            await asyncio.sleep(SSE_HEARTBEAT_SECONDS)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
