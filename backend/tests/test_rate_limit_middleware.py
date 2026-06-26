"""Edge rate-limit middleware tests."""

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient


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
async def test_rate_limit_headers_and_429(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeRedis()
    monkeypatch.setattr(
        "app.services.auth.edge_rate_limit.get_cache",
        AsyncMock(return_value=fake),
    )
    monkeypatch.setattr("app.core.rate_limit_middleware.settings.EDGE_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr("app.services.auth.edge_rate_limit.settings.DEFAULT_API_RATE_LIMIT_PER_MIN", 1)

    first = await client.get("/api/v1/datasets/")
    assert first.status_code in (200, 401, 403)
    assert first.headers.get("X-RateLimit-Limit") == "1"

    second = await client.get("/api/v1/datasets/")
    assert second.status_code == 429
    assert second.headers.get("X-RateLimit-Remaining") == "0"
    assert second.json()["errors"][0]["code"] == "RATE_LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_rate_limit_exempt_health(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeRedis()
    monkeypatch.setattr(
        "app.services.auth.edge_rate_limit.get_cache",
        AsyncMock(return_value=fake),
    )
    monkeypatch.setattr("app.core.rate_limit_middleware.settings.EDGE_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr("app.services.auth.edge_rate_limit.settings.DEFAULT_API_RATE_LIMIT_PER_MIN", 1)

    for _ in range(3):
        response = await client.get("/api/v1/health/live")
        assert response.status_code == 200
        assert "X-RateLimit-Limit" not in response.headers
