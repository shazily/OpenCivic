"""SCIM suspend revokes refresh-token families."""

import os
import uuid

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidToken
from app.db.models import User
from app.services.auth.refresh_service import RefreshService


@pytest.mark.asyncio
async def test_scim_suspend_revokes_refresh_sessions(db_session: AsyncSession) -> None:
    from app.services.auth import scim_service

    tenant_id = uuid.UUID(os.environ["DEV_TENANT_ID"])
    developer_id = uuid.UUID(os.environ["DEV_DEVELOPER_USER_ID"])

    refresh_service = RefreshService()
    token, _family = await refresh_service.create_session(
        user_id=developer_id,
        tenant_id=tenant_id,
        roles=["developer"],
    )
    session = await refresh_service.load_session(token)
    assert session.user_id == developer_id

    user = await db_session.scalar(select(User).where(User.id == developer_id))
    assert user is not None

    await scim_service.suspend_user(db_session, user, reason="test_suspend_sessions")
    await db_session.commit()

    with pytest.raises(InvalidToken):
        await refresh_service.load_session(token)

    await db_session.execute(
        update(User).where(User.id == developer_id).values(status="active")
    )
    await db_session.commit()
