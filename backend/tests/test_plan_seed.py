"""Default platform plan seed tests."""

import pytest
from sqlalchemy import func, select

import app.db.session as db_session_module
from app.db.models import Plan
from app.services.platform.plan_seed_service import ensure_default_plans


@pytest.mark.asyncio
async def test_ensure_default_plans_idempotent() -> None:
    db_session_module._ensure_engines()
    assert db_session_module.AsyncWriteSession is not None

    async with db_session_module.AsyncWriteSession() as session:
        first = await ensure_default_plans(session)
        second = await ensure_default_plans(session)
        count = await session.scalar(select(func.count()).select_from(Plan))
        await session.commit()

    assert first == 3 or first == 0
    assert second == 0
    assert count is not None
    assert count >= 3
