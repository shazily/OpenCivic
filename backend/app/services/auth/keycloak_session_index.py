"""Index Keycloak refresh tokens per platform user for SCIM session revoke."""

from __future__ import annotations

import json
import uuid

import structlog

from app.core.cache import cache_delete, cache_get, cache_set
from app.core.config import settings
from app.services.auth.keycloak_client import KeycloakTokenClient

logger = structlog.get_logger(__name__)

_PREFIX = "keycloak:refresh:user:"


def _user_key(user_id: uuid.UUID) -> str:
    return f"{_PREFIX}{user_id}"


async def register_keycloak_refresh(user_id: uuid.UUID, refresh_token: str) -> None:
    """Track a Keycloak refresh token issued at OIDC sign-in."""
    key = _user_key(user_id)
    raw = await cache_get(key)
    tokens: list[str] = json.loads(raw) if raw else []
    if refresh_token not in tokens:
        tokens.append(refresh_token)
    await cache_set(key, json.dumps(tokens), ttl_seconds=settings.REFRESH_COOKIE_MAX_AGE_SECONDS)


async def unregister_keycloak_refresh(user_id: uuid.UUID, refresh_token: str) -> None:
    """Remove a single refresh token from the user index (logout)."""
    key = _user_key(user_id)
    raw = await cache_get(key)
    if not raw:
        return
    tokens: list[str] = json.loads(raw)
    if refresh_token not in tokens:
        return
    tokens.remove(refresh_token)
    if tokens:
        await cache_set(key, json.dumps(tokens), ttl_seconds=settings.REFRESH_COOKIE_MAX_AGE_SECONDS)
    else:
        await cache_delete(key)


async def revoke_keycloak_sessions_for_user(user_id: uuid.UUID) -> int:
    """Revoke all indexed Keycloak refresh tokens for a user (best-effort)."""
    key = _user_key(user_id)
    raw = await cache_get(key)
    if not raw:
        return 0
    tokens: list[str] = json.loads(raw)
    client = KeycloakTokenClient()
    for token in tokens:
        await client.revoke_refresh_token(token)
    await cache_delete(key)
    logger.info("keycloak_sessions_revoked", user_id=str(user_id), count=len(tokens))
    return len(tokens)
