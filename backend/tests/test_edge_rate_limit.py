"""Edge rate limit and API key cache unit tests."""

import uuid

import pytest

from app.services.auth.api_key_cache import (
    CachedApiKeyIdentity,
    api_key_cache_key,
    get_cached_api_key_identity,
    invalidate_api_key_cache,
    set_cached_api_key_identity,
)
from app.services.auth.edge_rate_limit import (
    build_rate_limit_bucket,
    consume_rate_limit,
    resolve_limit_per_minute,
)


def test_resolve_limit_prefers_api_key_override() -> None:
    assert resolve_limit_per_minute(rate_limit_override=50, tenant_limit=200) == 50


def test_resolve_limit_uses_tenant_when_no_override() -> None:
    assert resolve_limit_per_minute(rate_limit_override=None, tenant_limit=200) == 200


def test_build_rate_limit_bucket_prefers_api_key() -> None:
    api_key_id = uuid.uuid4()
    bucket = build_rate_limit_bucket(
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        api_key_id=api_key_id,
        auth_type="api_key",
        client_fingerprint="1.2.3.4",
    )
    assert f"ratelimit:apikey:{api_key_id}:" in bucket


@pytest.mark.asyncio
async def test_api_key_cache_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    store: dict[str, str] = {}

    async def fake_get(key: str) -> str | None:
        return store.get(key)

    async def fake_set(key: str, value: str, ttl_seconds: int | None = None) -> None:
        store[key] = value

    async def fake_delete(key: str) -> None:
        store.pop(key, None)

    monkeypatch.setattr("app.services.auth.api_key_cache.cache_get", fake_get)
    monkeypatch.setattr("app.services.auth.api_key_cache.cache_set", fake_set)
    monkeypatch.setattr("app.services.auth.api_key_cache.cache_delete", fake_delete)

    identity = CachedApiKeyIdentity(
        user_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        roles=["developer"],
        api_key_id=uuid.uuid4(),
        rate_limit_per_min=250,
    )
    key_hash = "abc123"
    await set_cached_api_key_identity(key_hash, identity)
    loaded = await get_cached_api_key_identity(key_hash)
    assert loaded is not None
    assert loaded.user_id == identity.user_id
    assert loaded.rate_limit_per_min == 250

    await invalidate_api_key_cache(key_hash)
    assert await get_cached_api_key_identity(key_hash) is None
    assert api_key_cache_key(key_hash).startswith("apikey:identity:")


@pytest.mark.asyncio
async def test_consume_rate_limit_returns_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    counts: dict[str, int] = {}

    class FakeRedis:
        async def incr(self, key: str) -> int:
            counts[key] = counts.get(key, 0) + 1
            return counts[key]

        async def expire(self, key: str, ttl: int) -> None:
            return None

        async def get(self, key: str) -> str | None:
            return None

    async def fake_get_cache() -> FakeRedis:
        return FakeRedis()

    monkeypatch.setattr("app.services.auth.edge_rate_limit.get_cache", fake_get_cache)
    monkeypatch.setattr("app.services.auth.edge_rate_limit.settings.DEFAULT_API_RATE_LIMIT_PER_MIN", 2)

    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    first = await consume_rate_limit(
        tenant_id=tenant_id,
        user_id=user_id,
        api_key_id=None,
        auth_type="jwt",
        client_fingerprint=None,
    )
    assert first.allowed is True
    assert first.remaining == 1
    assert "X-RateLimit-Limit" in first.as_headers()

    second = await consume_rate_limit(
        tenant_id=tenant_id,
        user_id=user_id,
        api_key_id=None,
        auth_type="jwt",
        client_fingerprint=None,
    )
    assert second.allowed is True

    third = await consume_rate_limit(
        tenant_id=tenant_id,
        user_id=user_id,
        api_key_id=None,
        auth_type="jwt",
        client_fingerprint=None,
    )
    assert third.allowed is False
    assert third.remaining == 0
