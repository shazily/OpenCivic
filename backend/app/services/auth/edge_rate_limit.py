"""Per-tenant and per-API-key rate limiting at the gateway edge (Valkey-backed)."""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass

import structlog

from app.core.cache import get_cache
from app.core.config import settings
from app.services.auth.gateway_headers import (
    GATEWAY_API_KEY_ID_HEADER,
    GATEWAY_AUTH_TYPE_HEADER,
    GATEWAY_TENANT_HEADER,
    GATEWAY_USER_HEADER,
    RATE_LIMIT_LIMIT_HEADER,
    RATE_LIMIT_REMAINING_HEADER,
    RATE_LIMIT_RESET_HEADER,
)

logger = structlog.get_logger(__name__)

TENANT_LIMIT_CACHE_PREFIX = "tenant:ratelimit:"
TENANT_LIMIT_CACHE_TTL = 3600


@dataclass(frozen=True)
class RateLimitDecision:
    """Result of an edge rate-limit check."""

    allowed: bool
    limit: int
    remaining: int
    reset_epoch: int

    def as_headers(self) -> dict[str, str]:
        return {
            RATE_LIMIT_LIMIT_HEADER: str(self.limit),
            RATE_LIMIT_REMAINING_HEADER: str(self.remaining),
            RATE_LIMIT_RESET_HEADER: str(self.reset_epoch),
        }


def _current_window() -> tuple[int, int]:
    window = int(time.time() // 60)
    reset_epoch = (window + 1) * 60
    return window, reset_epoch


def resolve_limit_per_minute(
    *,
    rate_limit_override: int | None = None,
    tenant_limit: int | None = None,
) -> int:
    """Resolve effective per-minute limit for a client identity."""
    if rate_limit_override is not None and rate_limit_override > 0:
        return rate_limit_override
    if tenant_limit is not None and tenant_limit > 0:
        return tenant_limit
    return settings.DEFAULT_API_RATE_LIMIT_PER_MIN


def build_rate_limit_bucket(
    *,
    tenant_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
    api_key_id: uuid.UUID | None,
    auth_type: str | None,
    client_fingerprint: str | None,
) -> str:
    """Build a stable Valkey bucket id — API key > tenant user > anonymous IP."""
    window, _ = _current_window()
    if api_key_id is not None:
        return f"ratelimit:apikey:{api_key_id}:{window}"
    if tenant_id is not None and user_id is not None:
        return f"ratelimit:tenant:{tenant_id}:user:{user_id}:{window}"
    if tenant_id is not None:
        return f"ratelimit:tenant:{tenant_id}:{window}"
    fingerprint = client_fingerprint or "anonymous"
    digest = hashlib.sha256(fingerprint.encode()).hexdigest()[:24]
    return f"ratelimit:ip:{digest}:{window}"


async def get_tenant_rate_limit(tenant_id: uuid.UUID) -> int | None:
    """Load tenant plan rate limit from Valkey cache (defaults applied by caller)."""
    try:
        client = await get_cache()
        cached = await client.get(f"{TENANT_LIMIT_CACHE_PREFIX}{tenant_id}")
        if cached is not None:
            return int(cached)
    except Exception as exc:
        logger.warning("tenant_rate_limit_cache_read_failed", error=str(exc))
    return None


async def cache_tenant_rate_limit(tenant_id: uuid.UUID, limit: int) -> None:
    """Cache tenant plan limit for edge lookups."""
    try:
        client = await get_cache()
        await client.setex(f"{TENANT_LIMIT_CACHE_PREFIX}{tenant_id}", TENANT_LIMIT_CACHE_TTL, str(limit))
    except Exception as exc:
        logger.warning("tenant_rate_limit_cache_write_failed", error=str(exc))


async def consume_rate_limit(
    *,
    tenant_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
    api_key_id: uuid.UUID | None,
    auth_type: str | None,
    rate_limit_override: int | None = None,
    client_fingerprint: str | None = None,
) -> RateLimitDecision:
    """Increment Valkey counter and return allow/deny with standard headers."""
    window, reset_epoch = _current_window()
    tenant_limit = await get_tenant_rate_limit(tenant_id) if tenant_id else None
    limit = resolve_limit_per_minute(
        rate_limit_override=rate_limit_override,
        tenant_limit=tenant_limit,
    )
    bucket = build_rate_limit_bucket(
        tenant_id=tenant_id,
        user_id=user_id,
        api_key_id=api_key_id,
        auth_type=auth_type,
        client_fingerprint=client_fingerprint,
    )

    try:
        client = await get_cache()
        count = await client.incr(bucket)
        if count == 1:
            await client.expire(bucket, 70)
        remaining = max(0, limit - int(count))
        allowed = int(count) <= limit
    except Exception as exc:
        logger.warning("edge_rate_limit_cache_unavailable", error=str(exc))
        return RateLimitDecision(
            allowed=True,
            limit=limit,
            remaining=limit,
            reset_epoch=reset_epoch,
        )

    return RateLimitDecision(
        allowed=allowed,
        limit=limit,
        remaining=remaining if allowed else 0,
        reset_epoch=reset_epoch,
    )


def rate_limit_from_gateway_headers(headers: dict[str, str]) -> tuple[
    uuid.UUID | None,
    uuid.UUID | None,
    uuid.UUID | None,
    str | None,
]:
    """Extract identity fields from trusted gateway headers for direct API hits."""
    tenant_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    api_key_id: uuid.UUID | None = None
    auth_type = headers.get(GATEWAY_AUTH_TYPE_HEADER)

    try:
        if headers.get(GATEWAY_TENANT_HEADER):
            tenant_id = uuid.UUID(headers[GATEWAY_TENANT_HEADER])
        if headers.get(GATEWAY_USER_HEADER):
            user_id = uuid.UUID(headers[GATEWAY_USER_HEADER])
        if headers.get(GATEWAY_API_KEY_ID_HEADER):
            api_key_id = uuid.UUID(headers[GATEWAY_API_KEY_ID_HEADER])
    except ValueError:
        return None, None, None, auth_type

    return tenant_id, user_id, api_key_id, auth_type
