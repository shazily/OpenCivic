"""MFA enforcement for privileged roles when MFA_ENFORCEMENT_ENABLED is set."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import PermissionDenied
from app.db.models import User

MFA_REQUIRED_ROLES = frozenset(
    {
        "org_admin",
        "data_steward",
        "data_publisher",
        "developer",
    }
)


async def assert_mfa_enrolled(session: AsyncSession, user_id: uuid.UUID, roles: list[str]) -> None:
    """Block privileged actions when MFA is mandatory but not enabled on the user."""
    if not settings.MFA_ENFORCEMENT_ENABLED:
        return
    if not any(role in MFA_REQUIRED_ROLES for role in roles):
        return

    user = await session.scalar(select(User).where(User.id == user_id))
    if user is None or not user.mfa_enabled:
        raise PermissionDenied(
            message="Multi-factor authentication is required for this action. Enable MFA in your account settings.",
        )
