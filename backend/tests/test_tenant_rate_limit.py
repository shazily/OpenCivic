"""Tenant rate limit hydration tests."""

import uuid

import pytest

from app.services.platform.tenant_rate_limit_service import (
    hydrate_tenant_rate_limit,
    resolve_rate_limit_for_tier,
)


def test_resolve_rate_limit_uses_plan_when_present() -> None:
    assert resolve_rate_limit_for_tier("standard", plan_limit=750) == 750


def test_resolve_rate_limit_falls_back_to_tier() -> None:
    assert resolve_rate_limit_for_tier("professional", plan_limit=None) == 2500


@pytest.mark.asyncio
async def test_hydrate_tenant_rate_limit_writes_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    cached: dict[str, int] = {}

    async def fake_cache(tenant_id: uuid.UUID, limit: int) -> None:
        cached[str(tenant_id)] = limit

    monkeypatch.setattr(
        "app.services.platform.tenant_rate_limit_service.cache_tenant_rate_limit",
        fake_cache,
    )

    class FakeSession:
        async def scalar(self, _query: object) -> None:
            return None

    tenant_id = uuid.uuid4()
    limit = await hydrate_tenant_rate_limit(FakeSession(), tenant_id, tier="standard")
    assert limit == 1000
    assert cached[str(tenant_id)] == 1000


@pytest.mark.asyncio
async def test_hydrate_tenant_rate_limit_uses_plan_row(monkeypatch: pytest.MonkeyPatch) -> None:
    cached: dict[str, int] = {}

    async def fake_cache(tenant_id: uuid.UUID, limit: int) -> None:
        cached[str(tenant_id)] = limit

    monkeypatch.setattr(
        "app.services.platform.tenant_rate_limit_service.cache_tenant_rate_limit",
        fake_cache,
    )

    class FakePlan:
        api_rate_limit_per_min = 1200

    class FakeSession:
        async def scalar(self, _query: object) -> FakePlan:
            return FakePlan()

    tenant_id = uuid.uuid4()
    limit = await hydrate_tenant_rate_limit(FakeSession(), tenant_id, tier="standard")
    assert limit == 1200
    assert cached[str(tenant_id)] == 1200
