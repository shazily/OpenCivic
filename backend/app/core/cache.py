"""OpenCivic — Valkey (Redis-compatible) cache client. Lua scripting disabled per CVE mitigation."""

import structlog
from redis.asyncio import Redis, from_url

from app.core.config import settings

logger = structlog.get_logger(__name__)
_client: Redis | None = None


async def get_cache() -> Redis:
    global _client
    if _client is None:
        _client = from_url(
            settings.VALKEY_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
        )
    return _client


def reset_cache_client() -> None:
    """Reset the singleton client (used in tests after settings change)."""
    global _client
    _client = None


async def verify_cache_connection() -> None:
    try:
        client = await get_cache()
        await client.ping()
        logger.info("cache_connection_verified")
    except Exception as e:
        logger.error("cache_connection_failed", error=str(e))
        raise


async def cache_get(key: str) -> str | None:
    client = await get_cache()
    return await client.get(key)


async def cache_set(key: str, value: str, ttl_seconds: int | None = None) -> None:
    client = await get_cache()
    if ttl_seconds:
        await client.setex(key, ttl_seconds, value)
    else:
        await client.set(key, value)


async def cache_delete(key: str) -> None:
    client = await get_cache()
    await client.delete(key)


async def cache_incr(key: str) -> int:
    client = await get_cache()
    return await client.incr(key)


class _CacheFacade:
    """Thin facade for token blocklist helpers used by security.py."""

    async def exists(self, key: str) -> bool:
        client = await get_cache()
        return bool(await client.exists(key))

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        await cache_set(key, value, ttl_seconds=ex)


cache = _CacheFacade()
