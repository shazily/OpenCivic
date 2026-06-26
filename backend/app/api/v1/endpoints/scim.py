"""SCIM 2.0 provisioning — deprovision webhook and CRUD user resources."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.scim_auth import require_scim_token
from app.core.config import settings
from app.core.errors import AuthenticationRequired, NotFound, ValidationError
from app.db.models import User
from app.db.session import tenant_write_session
from app.services.auth import scim_service
from app.services.auth.scim_webhook_verifier import verify_scim_webhook_request

router = APIRouter()
logger = structlog.get_logger(__name__)


class ScimDeprovisionRequest(BaseModel):
    """Minimal SCIM delete payload mapped from Azure AD / Okta webhooks."""

    scim_external_id: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=255)


class ScimWebhookEvent(BaseModel):
    """IdP push notification for user lifecycle events (Azure AD / Okta compatible)."""

    event: str = Field(..., max_length=100)
    data: ScimDeprovisionRequest


async def _suspend_by_identifiers(
    session: AsyncSession,
    *,
    scim_external_id: str | None,
    email: str | None,
    reason: str,
) -> User:
    if not scim_external_id and not email:
        raise ValidationError(
            message="scim_external_id or email is required.",
            field="scim_external_id",
        )
    query = select(User)
    if scim_external_id:
        query = query.where(User.scim_external_id == scim_external_id)
    else:
        query = query.where(User.email == email)
    user = await session.scalar(query)
    if user is None:
        raise NotFound(message="User not found for SCIM deprovision.")
    return await scim_service.suspend_user(session, user, reason=reason)


class ScimUserCreate(BaseModel):
    """SCIM 2.0 User create body (minimal subset)."""

    userName: str = Field(..., max_length=255)
    name: dict[str, str] | None = None
    active: bool = True
    externalId: str | None = Field(default=None, max_length=255)
    emails: list[dict[str, object]] | None = None


class ScimUserPatch(BaseModel):
    """SCIM 2.0 User patch body (minimal subset)."""

    active: bool | None = None
    name: dict[str, str] | None = None
    externalId: str | None = Field(default=None, max_length=255)


def _tenant_id() -> uuid.UUID:
    return uuid.UUID(settings.DEV_TENANT_ID)


def _scim_list_response(resources: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
        "totalResults": len(resources),
        "Resources": resources,
        "startIndex": 1,
        "itemsPerPage": len(resources),
    }


@router.post("/deprovision")
async def scim_deprovision(request: Request) -> dict:
    """
    Suspend a user immediately when an IdP SCIM delete event is received.
    Protected by X-SCIM-Token or X-SCIM-Signature HMAC.
    """
    raw = await request.body()
    await verify_scim_webhook_request(request, raw)
    body = ScimDeprovisionRequest.model_validate_json(raw)

    tenant_id = _tenant_id()
    async with tenant_write_session(tenant_id) as session:
        user = await _suspend_by_identifiers(
            session,
            scim_external_id=body.scim_external_id,
            email=body.email,
            reason="scim_deprovision",
        )
        await session.commit()
        logger.info("scim_user_deprovisioned", user_id=str(user.id))
        return {
            "data": {"user_id": str(user.id), "status": "suspended"},
            "meta": {},
            "errors": [],
        }


@router.post("/webhook")
async def scim_webhook_event(request: Request) -> dict:
    """Handle IdP push notifications — suspends users on delete/deactivate events."""
    raw = await request.body()
    await verify_scim_webhook_request(request, raw)
    body = ScimWebhookEvent.model_validate_json(raw)

    normalized = body.event.strip().lower().replace(".", "_")
    if normalized not in {"user_deleted", "user_deactivated", "user_deprovisioned"}:
        return {
            "data": {"status": "ignored", "event": body.event},
            "meta": {},
            "errors": [],
        }

    tenant_id = _tenant_id()
    async with tenant_write_session(tenant_id) as session:
        user = await _suspend_by_identifiers(
            session,
            scim_external_id=body.data.scim_external_id,
            email=body.data.email,
            reason=f"scim_webhook_{normalized}",
        )
        await session.commit()
        logger.info("scim_webhook_processed", user_id=str(user.id), event=body.event)
        return {
            "data": {"user_id": str(user.id), "status": "suspended", "event": body.event},
            "meta": {},
            "errors": [],
        }


@router.get("/v2/Users")
async def scim_list_users(
    _: None = Depends(require_scim_token),
    filter: str | None = Query(default=None),
) -> dict[str, object]:
    """List users — supports filter=userName eq \"email\"."""
    email_filter: str | None = None
    if filter and "userName eq" in filter:
        email_filter = filter.split('"')[1] if '"' in filter else None

    tenant_id = _tenant_id()
    async with tenant_write_session(tenant_id) as session:
        users = await scim_service.list_users(session, filter_email=email_filter)
        resources = [scim_service.user_to_scim(user) for user in users]
    return _scim_list_response(resources)


@router.post("/v2/Users", status_code=201)
async def scim_create_user(
    body: ScimUserCreate,
    _: None = Depends(require_scim_token),
) -> dict[str, object]:
    """Provision a new tenant user."""
    display_name = (body.name or {}).get("formatted") or body.userName
    tenant_id = _tenant_id()
    async with tenant_write_session(tenant_id) as session:
        user = await scim_service.create_user(
            session,
            tenant_id=tenant_id,
            email=body.userName,
            name=display_name,
            scim_external_id=body.externalId,
        )
        if not body.active:
            await session.execute(
                update(User).where(User.id == user.id).values(status="suspended")
            )
            await session.refresh(user)
        await session.commit()
        return scim_service.user_to_scim(user)


@router.get("/v2/Users/{user_id}")
async def scim_get_user(
    user_id: uuid.UUID,
    _: None = Depends(require_scim_token),
) -> dict[str, object]:
    """Fetch a SCIM user by platform id."""
    tenant_id = _tenant_id()
    async with tenant_write_session(tenant_id) as session:
        user = await scim_service.get_user(session, user_id)
        return scim_service.user_to_scim(user)


@router.patch("/v2/Users/{user_id}")
async def scim_patch_user(
    user_id: uuid.UUID,
    body: ScimUserPatch,
    _: None = Depends(require_scim_token),
) -> dict[str, object]:
    """Patch SCIM user fields (active, name, externalId)."""
    tenant_id = _tenant_id()
    async with tenant_write_session(tenant_id) as session:
        user = await scim_service.get_user(session, user_id)
        display_name = (body.name or {}).get("formatted") if body.name else None
        updated = await scim_service.patch_user(
            session,
            user,
            active=body.active,
            name=display_name,
            scim_external_id=body.externalId,
        )
        await session.commit()
        return scim_service.user_to_scim(updated)


@router.delete("/v2/Users/{user_id}")
async def scim_delete_user(
    user_id: uuid.UUID,
    _: None = Depends(require_scim_token),
) -> dict[str, object]:
    """Suspend user on SCIM delete."""
    tenant_id = _tenant_id()
    async with tenant_write_session(tenant_id) as session:
        user = await scim_service.get_user(session, user_id)
        updated = await scim_service.suspend_user(session, user, reason="scim_delete")
        await session.commit()
        return scim_service.user_to_scim(updated)
