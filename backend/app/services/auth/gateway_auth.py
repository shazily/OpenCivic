"""APISIX forward-auth decision logic — validates JWT/API keys at the edge."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.errors import AuthenticationRequired, InvalidToken
from app.core.security import hash_api_key
from app.db.models import ApiKey, User
from app.db.session import set_tenant_context
from app.services.auth.api_key_cache import (
    CachedApiKeyIdentity,
    get_cached_api_key_identity,
    is_cache_fresh,
    set_cached_api_key_identity,
)
from app.services.auth.edge_rate_limit import consume_rate_limit
from app.services.auth.gateway_headers import (
    GATEWAY_API_KEY_ID_HEADER,
    GATEWAY_AUTH_TYPE_HEADER,
    GATEWAY_ROLES_HEADER,
    GATEWAY_TENANT_HEADER,
    GATEWAY_TRUST_HEADER,
    GATEWAY_USER_HEADER,
)

_PUBLIC_EXACT = frozenset(
    {
        "/api/v1/health/live",
        "/api/v1/health/ready",
        "/api/v1/auth/config",
        "/api/v1/openapi.json",
    }
)
_PUBLIC_PREFIXES = (
    "/api/v1/portal/",
    "/api/v1/auth/",
    "/api/v1/internal/",
    "/api/v1/scim/",
)
_OPTIONAL_PREFIXES = (
    "/api/v1/datasets",
    "/api/v1/search",
    "/api/v1/feedback",
    "/api/v1/analytics",
)


class GatewayAuthMode(str, Enum):
    PUBLIC = "public"
    OPTIONAL = "optional"
    REQUIRED = "required"


@dataclass(frozen=True)
class GatewayIdentity:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    roles: list[str]
    auth_type: str
    api_key_id: uuid.UUID | None = None
    rate_limit_per_min: int | None = None


def classify_gateway_path(method: str, uri: str) -> GatewayAuthMode:
    """Return whether the path is public, optionally authenticated, or protected."""
    if method.upper() == "OPTIONS":
        return GatewayAuthMode.PUBLIC

    path = uri.split("?", 1)[0].rstrip("/") or "/"
    if path in _PUBLIC_EXACT:
        return GatewayAuthMode.PUBLIC
    if any(path.startswith(prefix) for prefix in _PUBLIC_PREFIXES):
        return GatewayAuthMode.PUBLIC
    if any(path.startswith(prefix) for prefix in _OPTIONAL_PREFIXES):
        return GatewayAuthMode.OPTIONAL
    return GatewayAuthMode.REQUIRED


def extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


def extract_api_key(authorization: str | None, x_api_key: str | None) -> str | None:
    if x_api_key and x_api_key.startswith("oc_"):
        return x_api_key.strip()
    token = extract_bearer_token(authorization)
    if token and token.startswith("oc_"):
        return token
    return None


def build_gateway_trust_headers(identity: GatewayIdentity | None) -> dict[str, str]:
    """Headers APISIX forwards to FastAPI after successful forward-auth."""
    if not settings.GATEWAY_AUTH_SECRET:
        return {}
    headers = {GATEWAY_TRUST_HEADER: settings.GATEWAY_AUTH_SECRET}
    if identity is None:
        return headers
    headers[GATEWAY_USER_HEADER] = str(identity.user_id)
    headers[GATEWAY_TENANT_HEADER] = str(identity.tenant_id)
    headers[GATEWAY_ROLES_HEADER] = ",".join(identity.roles)
    headers[GATEWAY_AUTH_TYPE_HEADER] = identity.auth_type
    if identity.api_key_id is not None:
        headers[GATEWAY_API_KEY_ID_HEADER] = str(identity.api_key_id)
    return headers


async def resolve_gateway_identity(
    authorization: str | None,
    x_api_key: str | None,
) -> GatewayIdentity | None:
    """Validate JWT or API key material for APISIX forward-auth."""
    api_key_raw = extract_api_key(authorization, x_api_key)
    if api_key_raw:
        return await _resolve_api_key_identity(api_key_raw)

    token = extract_bearer_token(authorization)
    if not token:
        return None

    from app.api.v1.dependencies.auth import _authenticate_token

    user = await _authenticate_token(token)
    return GatewayIdentity(
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        roles=user.roles,
        auth_type="jwt",
    )


async def _resolve_api_key_identity(raw_key: str) -> GatewayIdentity:
    key_hash = hash_api_key(raw_key)
    cached = await get_cached_api_key_identity(key_hash)
    if cached is not None:
        return GatewayIdentity(
            user_id=cached.user_id,
            tenant_id=cached.tenant_id,
            roles=cached.roles,
            auth_type="api_key",
            api_key_id=cached.api_key_id,
            rate_limit_per_min=cached.rate_limit_per_min,
        )

    engine = create_async_engine(settings.database_migration_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            api_key = await session.scalar(select(ApiKey).where(ApiKey.key_hash == key_hash))
            if api_key is None or api_key.revoked_at is not None:
                raise InvalidToken(message="Invalid API key.")
            if api_key.expires_at is not None and api_key.expires_at < datetime.now(UTC):
                raise InvalidToken(message="API key has expired.")

            await set_tenant_context(session, api_key.tenant_id)
            owner = await session.scalar(select(User).where(User.id == api_key.owner_id))
            if owner is None:
                raise InvalidToken(message="API key owner not found.")

            if is_cache_fresh(api_key.last_used_at):
                api_key.last_used_at = datetime.now(UTC)
                await session.commit()

            identity = GatewayIdentity(
                user_id=owner.id,
                tenant_id=api_key.tenant_id,
                roles=list(owner.roles or []),
                auth_type="api_key",
                api_key_id=api_key.id,
                rate_limit_per_min=api_key.rate_limit_override,
            )
            await set_cached_api_key_identity(
                key_hash,
                CachedApiKeyIdentity(
                    user_id=identity.user_id,
                    tenant_id=identity.tenant_id,
                    roles=identity.roles,
                    api_key_id=identity.api_key_id,  # type: ignore[arg-type]
                    rate_limit_per_min=identity.rate_limit_per_min,
                ),
            )
            return identity
    finally:
        await engine.dispose()


async def evaluate_gateway_auth(
    method: str,
    uri: str,
    authorization: str | None,
    x_api_key: str | None,
    client_fingerprint: str | None = None,
) -> tuple[int, dict[str, str]]:
    """Return HTTP status and response headers for APISIX forward-auth."""
    mode = classify_gateway_path(method, uri)
    if mode == GatewayAuthMode.PUBLIC:
        return 200, build_gateway_trust_headers(None)

    identity: GatewayIdentity | None
    try:
        identity = await resolve_gateway_identity(authorization, x_api_key)
    except (AuthenticationRequired, InvalidToken):
        identity = None

    if identity is None and mode == GatewayAuthMode.REQUIRED:
        return 401, {}

    headers = build_gateway_trust_headers(identity)
    if settings.GATEWAY_RATE_LIMIT_ENABLED:
        decision = await consume_rate_limit(
            tenant_id=identity.tenant_id if identity else None,
            user_id=identity.user_id if identity else None,
            api_key_id=identity.api_key_id if identity else None,
            auth_type=identity.auth_type if identity else None,
            rate_limit_override=identity.rate_limit_per_min if identity else None,
            client_fingerprint=client_fingerprint,
        )
        headers.update(decision.as_headers())
        if not decision.allowed:
            return 429, headers

    return 200, headers
