"""Developer webhook endpoints."""

import uuid

from fastapi import APIRouter, status

from app.api.v1.dependencies.permissions import DeveloperRequired
from app.db.session import ReadSession, WriteSession
from app.repositories.webhook_repository import WebhookRepository
from app.schemas.webhook import WebhookCreateRequest, WebhookResponse
from app.services.notifications.webhook_service import deliver_webhook_by_id

router = APIRouter()


@router.get("/")
async def list_webhooks(
    session: ReadSession,
    current_user: DeveloperRequired,
) -> dict:
    """List webhooks owned by the authenticated developer."""
    repo = WebhookRepository(session)
    items = await repo.list_for_owner(current_user.user_id)
    return {
        "data": [
            WebhookResponse.model_validate(item).model_dump(mode="json") for item in items
        ],
        "meta": {"total_count": len(items)},
        "errors": [],
    }


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_webhook(
    body: WebhookCreateRequest,
    session: WriteSession,
    current_user: DeveloperRequired,
) -> dict:
    """Register a webhook for dataset lifecycle events."""
    repo = WebhookRepository(session)
    webhook = await repo.create(
        tenant_id=current_user.tenant_id,
        owner_id=current_user.user_id,
        url=str(body.url),
        events=body.events,
        dataset_id=body.dataset_id,
    )
    return {
        "data": WebhookResponse.model_validate(webhook).model_dump(mode="json"),
        "meta": {},
        "errors": [],
    }


@router.delete("/{webhook_id}")
async def delete_webhook(
    webhook_id: uuid.UUID,
    session: WriteSession,
    current_user: DeveloperRequired,
) -> dict:
    """Remove a webhook subscription."""
    repo = WebhookRepository(session)
    await repo.delete(webhook_id, current_user.user_id)
    return {
        "data": {"id": str(webhook_id), "status": "deleted"},
        "meta": {},
        "errors": [],
    }


@router.post("/{webhook_id}/test", status_code=status.HTTP_202_ACCEPTED)
async def test_webhook(
    webhook_id: uuid.UUID,
    session: WriteSession,
    current_user: DeveloperRequired,
) -> dict:
    """Send a test payload to the webhook URL (synchronous delivery)."""
    repo = WebhookRepository(session)
    webhook = await repo.get_for_owner(webhook_id, current_user.user_id)
    result = await deliver_webhook_by_id(
        session,
        webhook.id,
        "WebhookTest",
        {"message": "OpenCivic webhook test delivery"},
    )
    await session.commit()
    return {"data": result, "meta": {}, "errors": []}
