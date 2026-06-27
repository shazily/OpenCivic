"""Edge rate-limit middleware tests."""

import time
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from app.services.auth.edge_rate_limit import RateLimitDecision, consume_rate_limit


class _FakeRedis:
    def __init__(self) -> None:
        self.count = 0

    async def incr(self, key: str) -> int:
        del key
        self.count += 1
        return self.count

    async def expire(self, key: str, ttl: int) -> bool:
        del key, ttl
        return True


@pytest.mark.asyncio
async def test_consume_rate_limit_blocks_after_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeRedis()
    monkeypatch.setattr(
        "app.services.auth.edge_rate_limit.get_cache",
        AsyncMock(return_value=fake),
    )
    monkeypatch.setattr("app.services.auth.edge_rate_limit.settings.DEFAULT_API_RATE_LIMIT_PER_MIN", 1)

    first = await consume_rate_limit(
        tenant_id=None,
        user_id=None,
        api_key_id=None,
        auth_type=None,
        client_fingerprint="unit-test-fingerprint",
    )
    assert first.allowed is True
    assert first.limit == 1
    assert first.remaining == 0

    second = await consume_rate_limit(
        tenant_id=None,
        user_id=None,
        api_key_id=None,
        auth_type=None,
        client_fingerprint="unit-test-fingerprint",
    )
    assert second.allowed is False
    assert second.remaining == 0


@pytest.mark.asyncio
async def test_rate_limit_middleware_returns_429(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    reset_epoch = int(time.time()) + 60
    monkeypatch.setattr("app.core.rate_limit_middleware.settings.EDGE_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(
        "app.core.rate_limit_middleware.consume_rate_limit",
        AsyncMock(
            return_value=RateLimitDecision(
                allowed=False,
                limit=1,
                remaining=0,
                reset_epoch=reset_epoch,
            )
        ),
    )

    response = await client.get("/api/v1/datasets/")
    assert response.status_code == 429
    assert response.headers.get("X-RateLimit-Limit") == "1"
    assert response.json()["errors"][0]["code"] == "RATE_LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_rate_limit_exempt_health(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.rate_limit_middleware.settings.EDGE_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(
        "app.core.rate_limit_middleware.consume_rate_limit",
        AsyncMock(
            return_value=RateLimitDecision(
                allowed=True,
                limit=1,
                remaining=0,
                reset_epoch=int(time.time()) + 60,
            )
        ),
    )

    for _ in range(3):
        response = await client.get("/api/v1/health/live")
        assert response.status_code == 200
        assert "X-RateLimit-Limit" not in response.headers
