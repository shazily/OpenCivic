"""In-app notification API tests."""

import os
import uuid

import pytest
from httpx import AsyncClient

from app.services.notifications.in_app_service import InAppNotificationService


@pytest.mark.asyncio
async def test_in_app_notification_list(client: AsyncClient) -> None:
    tenant_id = uuid.UUID(os.environ["DEV_TENANT_ID"])
    user_id = uuid.UUID(os.environ["DEV_STEWARD_USER_ID"])
    await InAppNotificationService.push(
        tenant_id=tenant_id,
        user_id=user_id,
        title="Test alert",
        body="SLA breach on dataset X",
        event_type="WorkflowSlaBreached",
    )
    headers = {"Authorization": f"Bearer {os.environ['DEV_STEWARD_AUTH_TOKEN']}"}
    response = await client.get("/api/v1/notifications/", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total_count"] >= 1
    assert any(item["title"] == "Test alert" for item in body["data"])


@pytest.mark.asyncio
async def test_in_app_notification_mark_read(client: AsyncClient) -> None:
    tenant_id = uuid.UUID(os.environ["DEV_TENANT_ID"])
    user_id = uuid.UUID(os.environ["DEV_STEWARD_USER_ID"])
    item = await InAppNotificationService.push(
        tenant_id=tenant_id,
        user_id=user_id,
        title="Unread item",
        body="Needs acknowledgement",
        event_type="TestEvent",
    )
    headers = {"Authorization": f"Bearer {os.environ['DEV_STEWARD_AUTH_TOKEN']}"}

    mark_response = await client.post(
        f"/api/v1/notifications/{item['id']}/read",
        headers=headers,
    )
    assert mark_response.status_code == 200

    count_response = await client.get("/api/v1/notifications/unread-count", headers=headers)
    assert count_response.status_code == 200
    unread = count_response.json()["data"]["unread_count"]
    assert isinstance(unread, int)

    read_all_response = await client.post("/api/v1/notifications/read-all", headers=headers)
    assert read_all_response.status_code == 200
    assert read_all_response.json()["data"]["marked_read"] >= 0
