"""Edge rate-limit middleware tests."""

import time
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from app.core.cache import reset_cache_client
from app.services.auth.edge_rate_limit import RateLimitDecision


@pytest.mark.asyncio
async def test_rate_limit_headers_and_429(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    reset_cache_client()
    calls = {"count": 0}
    reset_epoch = int(time.time()) + 60

    async def fake_consume_rate_limit(**_kwargs) -> RateLimitDecision:
        calls["count"] += 1
        if calls["count"] == 1:
            return RateLimitDecision(allowed=True, limit=1, remaining=0, reset_epoch=reset_epoch)
        return RateLimitDecision(allowed=False, limit=1, remaining=0, reset_epoch=reset_epoch)

    monkeypatch.setattr("app.core.rate_limit_middleware.settings.EDGE_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(
        "app.core.rate_limit_middleware.consume_rate_limit",
        fake_consume_rate_limit,
    )

    first = await client.get("/api/v1/datasets/")
    assert first.status_code in (200, 401, 403)
    assert first.headers.get("X-RateLimit-Limit") == "1"

    second = await client.get("/api/v1/datasets/")
    assert second.status_code == 429
    assert second.headers.get("X-RateLimit-Remaining") == "0"
    assert second.json()["errors"][0]["code"] == "RATE_LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_rate_limit_exempt_health(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    reset_cache_client()
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
