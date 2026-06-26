"""Connector management endpoints."""

import uuid

from fastapi import APIRouter

from app.api.v1.dependencies.permissions import AdminRequired
from app.db.session import ReadSession, WriteSession
from app.repositories.connector_repository import ConnectorRepository
from app.schemas.connector import ConnectorCreateRequest, ConnectorResponse
from app.services.connectors.base import ConnectorBase
from app.services.connectors.registry import get_connector, registered_types
from app.workers.tasks.tasks import sync_connector

router = APIRouter()


@router.get("/")
async def list_connectors(
    session: ReadSession,
    current_user: AdminRequired,
) -> dict:
    repo = ConnectorRepository(session)
    items = await repo.list_all()
    return {
        "data": [
            ConnectorResponse.model_validate(item).model_dump(mode="json") for item in items
        ],
        "meta": {"total_count": len(items), "types": registered_types()},
        "errors": [],
    }


@router.post("/", status_code=201)
async def create_connector(
    body: ConnectorCreateRequest,
    session: WriteSession,
    current_user: AdminRequired,
) -> dict:
    connector = await ConnectorRepository(session).create(
        tenant_id=current_user.tenant_id,
        name=body.name,
        type_name=body.type,
        config=body.config,
        created_by=current_user.user_id,
        dataset_id=body.dataset_id,
        sync_frequency=body.sync_frequency,
    )
    return {
        "data": ConnectorResponse.model_validate(connector).model_dump(mode="json"),
        "meta": {},
        "errors": [],
    }


@router.post("/{connector_id}/test")
async def test_connector(
    connector_id: uuid.UUID,
    session: ReadSession,
    current_user: AdminRequired,
) -> dict:
    connector = await ConnectorRepository(session).get_by_id(connector_id)
    config = ConnectorBase.parse_config(connector.config)
    plugin = get_connector(connector.type, config)
    result = await plugin.test_connection()
    return {
        "data": {"ok": result.ok, "message": result.message},
        "meta": {},
        "errors": [],
    }


@router.post("/{connector_id}/sync", status_code=202)
async def sync_connector_now(
    connector_id: uuid.UUID,
    session: ReadSession,
    current_user: AdminRequired,
) -> dict:
    await ConnectorRepository(session).get_by_id(connector_id)
    task = sync_connector.delay(str(connector_id), str(current_user.tenant_id))
    return {
        "data": {"job_id": task.id, "status": "queued"},
        "meta": {},
        "errors": [],
    }


@router.get("/{connector_id}/sync-history")
async def connector_sync_history(
    connector_id: uuid.UUID,
    session: ReadSession,
    current_user: AdminRequired,
) -> dict:
    """Recent connector sync events derived from connector state (v1 stub)."""
    from app.services.connectors.connector_sync_history import build_connector_sync_history

    connector = await ConnectorRepository(session).get_by_id(connector_id)
    history = build_connector_sync_history(connector)
    return {
        "data": history,
        "meta": {"total_count": len(history), "connector_id": str(connector_id)},
        "errors": [],
    }
