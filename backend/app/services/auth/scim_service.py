"""SCIM 2.0 user provisioning helpers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound, UserConflict, ValidationError
from app.db.models import ApiKey, User
from app.services.auth.keycloak_session_index import revoke_keycloak_sessions_for_user
from app.services.auth.refresh_service import RefreshService
from app.services.events.event_publisher import EventPublisher

_refresh_service = RefreshService()

SCIM_USER_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:User"


def user_to_scim(user: User) -> dict[str, object]:
    """Map a tenant user row to a minimal SCIM 2.0 User resource."""
    return {
        "schemas": [SCIM_USER_SCHEMA],
        "id": str(user.id),
        "userName": user.email,
        "name": {"formatted": user.name},
        "active": user.status == "active",
        "externalId": user.scim_external_id,
        "emails": [{"value": user.email, "primary": True}],
        "roles": list(user.roles),
    }


async def list_users(session: AsyncSession, *, filter_email: str | None = None) -> list[User]:
    """List tenant users, optionally filtered by email."""
    query = select(User).where(User.deleted_at.is_(None)).order_by(User.created_at.desc())
    if filter_email:
        query = query.where(User.email == filter_email)
    result = await session.scalars(query)
    return list(result.all())


async def create_user(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    email: str,
    name: str,
    scim_external_id: str | None,
    roles: list[str] | None = None,
) -> User:
    """Provision a user from a SCIM create request."""
    existing = await session.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise UserConflict(message="User with this email already exists.", field="userName")

    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        keycloak_user_id=f"scim-{uuid.uuid4().hex[:12]}",
        email=email,
        name=name,
        roles=roles or ["viewer"],
        scim_external_id=scim_external_id,
        status="active",
    )
    session.add(user)
    await session.flush()

    await EventPublisher.publish(
        session,
        tenant_id=tenant_id,
        event_type="UserProvisioned",
        aggregate_id=user.id,
        aggregate_type="user",
        actor_id=None,
        actor_type="system",
        payload={"email": email, "scim_external_id": scim_external_id},
    )
    return user


async def get_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    """Fetch a user by id."""
    user = await session.scalar(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    if user is None:
        raise NotFound(message="SCIM user not found.")
    return user


async def patch_user(
    session: AsyncSession,
    user: User,
    *,
    active: bool | None = None,
    name: str | None = None,
    scim_external_id: str | None = None,
) -> User:
    """Apply SCIM patch fields to a user."""
    values: dict[str, object] = {}
    if active is not None:
        values["status"] = "active" if active else "suspended"
    if name is not None:
        values["name"] = name
    if scim_external_id is not None:
        values["scim_external_id"] = scim_external_id
    if not values:
        raise ValidationError(message="No supported patch fields provided.", field="Operations")

    await session.execute(update(User).where(User.id == user.id).values(**values))
    await session.refresh(user)
    return user


async def revoke_api_keys_for_user(session: AsyncSession, user_id: uuid.UUID) -> int:
    """Revoke all active API keys owned by a user; returns count revoked."""
    now = datetime.now(UTC)
    result = await session.execute(
        update(ApiKey)
        .where(ApiKey.owner_id == user_id, ApiKey.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    return int(result.rowcount or 0)


async def suspend_user(session: AsyncSession, user: User, *, reason: str) -> User:
    """Suspend a user (SCIM delete / deprovision), revoke API keys and refresh sessions."""
    await session.execute(update(User).where(User.id == user.id).values(status="suspended"))
    revoked_keys = await revoke_api_keys_for_user(session, user.id)
    revoked_sessions = await _refresh_service.revoke_user_sessions(user.id)
    revoked_keycloak = await revoke_keycloak_sessions_for_user(user.id)
    await EventPublisher.publish(
        session,
        tenant_id=user.tenant_id,
        event_type="UserSuspended",
        aggregate_id=user.id,
        aggregate_type="user",
        actor_id=None,
        actor_type="system",
        payload={
            "reason": reason,
            "email": user.email,
            "api_keys_revoked": revoked_keys,
            "refresh_sessions_revoked": revoked_sessions,
            "keycloak_sessions_revoked": revoked_keycloak,
        },
    )
    await session.refresh(user)
    return user
