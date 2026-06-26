"""MFA enforcement service tests."""

import os
import uuid

import pytest
from sqlalchemy import update

from app.core.config import settings
from app.core.errors import PermissionDenied
from app.db.models import User
from app.db.session import tenant_write_session
from app.services.auth.mfa_enforcement import assert_mfa_enrolled


@pytest.mark.asyncio
async def test_mfa_enforcement_blocks_when_disabled_on_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "MFA_ENFORCEMENT_ENABLED", True)
    tenant_id = uuid.UUID(os.environ["DEV_TENANT_ID"])
    publisher_id = uuid.UUID(os.environ["DEV_USER_ID"])

    async with tenant_write_session(tenant_id) as session:
        await session.execute(
            update(User).where(User.id == publisher_id).values(mfa_enabled=False)
        )
        with pytest.raises(PermissionDenied):
            await assert_mfa_enrolled(session, publisher_id, ["data_publisher"])


@pytest.mark.asyncio
async def test_mfa_enforcement_skipped_when_flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "MFA_ENFORCEMENT_ENABLED", False)
    tenant_id = uuid.UUID(os.environ["DEV_TENANT_ID"])
    publisher_id = uuid.UUID(os.environ["DEV_USER_ID"])

    async with tenant_write_session(tenant_id) as session:
        await assert_mfa_enrolled(session, publisher_id, ["data_publisher"])
