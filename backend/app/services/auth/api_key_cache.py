"""Valkey-backed cache for validated API key identities at the gateway edge."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import structlog

from app.core.cache import cache_delete, cache_get, cache_set

logger = structlog.get_logger(__name__)

API_KEY_CACHE_PREFIX = "apikey:identity:"
API_KEY_CACHE_TTL_SECONDS = 300


@dataclass(frozen=True)
class CachedApiKeyIdentity:
    """Serializable API key identity stored in Valkey."""

    user_id: uuid.UUID
    tenant_id: uuid.UUID
    roles: list[str]
    api_key_id: uuid.UUID
    rate_limit_per_min: int | None

    def to_json(self) -> str:
        return json.dumps(
            {
                "user_id": str(self.user_id),
                "tenant_id": str(self.tenant_id),
                "roles": self.roles,
                "api_key_id": str(self.api_key_id),
                "rate_limit_per_min": self.rate_limit_per_min,
            }
        )

    @classmethod
    def from_json(cls, payload: str) -> CachedApiKeyIdentity | None:
        try:
            data = json.loads(payload)
            return cls(
                user_id=uuid.UUID(data["user_id"]),
                tenant_id=uuid.UUID(data["tenant_id"]),
                roles=list(data.get("roles") or []),
                api_key_id=uuid.UUID(data["api_key_id"]),
                rate_limit_per_min=data.get("rate_limit_per_min"),
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None


def api_key_cache_key(key_hash: str) -> str:
    return f"{API_KEY_CACHE_PREFIX}{key_hash}"


async def get_cached_api_key_identity(key_hash: str) -> CachedApiKeyIdentity | None:
    """Return cached identity for a validated API key hash, if present."""
    raw = await cache_get(api_key_cache_key(key_hash))
    if raw is None:
        return None
    identity = CachedApiKeyIdentity.from_json(raw)
    if identity is None:
        await cache_delete(api_key_cache_key(key_hash))
    return identity


async def set_cached_api_key_identity(key_hash: str, identity: CachedApiKeyIdentity) -> None:
    """Store validated API key identity for edge lookups."""
    await cache_set(
        api_key_cache_key(key_hash),
        identity.to_json(),
        ttl_seconds=API_KEY_CACHE_TTL_SECONDS,
    )


async def invalidate_api_key_cache(key_hash: str) -> None:
    """Drop cached identity when a key is revoked or rotated."""
    await cache_delete(api_key_cache_key(key_hash))
    logger.info("api_key_cache_invalidated", key_hash_prefix=key_hash[:8])


def is_cache_fresh(last_used_at: datetime | None) -> bool:
    """Skip cache when last_used_at is very recent to keep usage timestamps accurate."""
    if last_used_at is None:
        return True
    age = (datetime.now(UTC) - last_used_at).total_seconds()
    return age > 30
