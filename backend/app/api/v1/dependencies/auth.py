"""Auth dependencies. RULE: tenant_id ALWAYS from validated JWT — never from client."""

import uuid
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings, settings
from app.core.errors import AuthenticationRequired, InvalidToken
from app.core.security import jwt_validator
from app.services.auth.gateway_headers import (
    GATEWAY_ROLES_HEADER,
    GATEWAY_TENANT_HEADER,
    GATEWAY_TRUST_HEADER,
    GATEWAY_USER_HEADER,
)

bearer_scheme = HTTPBearer(auto_error=False)


class CurrentUser:
    """Authenticated user context extracted from a validated token."""

    def __init__(self, user_id: uuid.UUID, tenant_id: uuid.UUID, roles: list[str]) -> None:
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.roles = roles


def _resolve_dev_user(token: str) -> CurrentUser:
    """Dev-only auth — fixed tokens map to seeded tenant users."""
    if not settings.DEV_AUTH_ENABLED:
        raise InvalidToken(message="Development authentication is disabled.")
    if token == settings.DEV_STEWARD_AUTH_TOKEN:
        return CurrentUser(
            user_id=uuid.UUID(settings.DEV_STEWARD_USER_ID),
            tenant_id=uuid.UUID(settings.DEV_TENANT_ID),
            roles=["data_steward"],
        )
    if token == settings.DEV_ADMIN_AUTH_TOKEN:
        return CurrentUser(
            user_id=uuid.UUID(settings.DEV_ADMIN_USER_ID),
            tenant_id=uuid.UUID(settings.DEV_TENANT_ID),
            roles=["org_admin"],
        )
    if token == settings.DEV_DEVELOPER_AUTH_TOKEN:
        return CurrentUser(
            user_id=uuid.UUID(settings.DEV_DEVELOPER_USER_ID),
            tenant_id=uuid.UUID(settings.DEV_TENANT_ID),
            roles=["developer"],
        )
    if token == settings.DEV_AUTH_TOKEN:
        return CurrentUser(
            user_id=uuid.UUID(settings.DEV_USER_ID),
            tenant_id=uuid.UUID(settings.DEV_TENANT_ID),
            roles=["data_publisher"],
        )
    raise InvalidToken(message="Invalid development token.")


def _user_from_gateway_headers(request: Request) -> CurrentUser | None:
    """Trust identity headers injected by APISIX after forward-auth validation."""
    active_settings = get_settings()
    if not active_settings.EDGE_AUTH_ENABLED or not active_settings.GATEWAY_AUTH_SECRET:
        return None
    if request.headers.get(GATEWAY_TRUST_HEADER) != active_settings.GATEWAY_AUTH_SECRET:
        return None
    user_raw = request.headers.get(GATEWAY_USER_HEADER)
    tenant_raw = request.headers.get(GATEWAY_TENANT_HEADER)
    if not user_raw or not tenant_raw:
        return None
    roles_raw = request.headers.get(GATEWAY_ROLES_HEADER, "")
    roles = [role.strip() for role in roles_raw.split(",") if role.strip()]
    return CurrentUser(
        user_id=uuid.UUID(user_raw),
        tenant_id=uuid.UUID(tenant_raw),
        roles=roles,
    )


async def _resolve_keycloak_user(token: str) -> CurrentUser:
    """Validate Keycloak JWT and map claims to a platform user row."""
    from app.db.session import AsyncReadSession, _ensure_engines, set_tenant_context
    from app.services.auth.user_resolver import resolve_user_from_claims

    claims = await jwt_validator.validate_token(token, settings.KEYCLOAK_REALM)
    tenant_raw = claims.get("tenant_id", settings.DEV_TENANT_ID)
    tenant_id = uuid.UUID(str(tenant_raw))

    _ensure_engines()
    async with AsyncReadSession() as session:
        await set_tenant_context(session, tenant_id)
        return await resolve_user_from_claims(session, claims)


async def _authenticate_token(token: str) -> CurrentUser:
    if settings.DEV_AUTH_ENABLED and token in (
        settings.DEV_AUTH_TOKEN,
        settings.DEV_STEWARD_AUTH_TOKEN,
        settings.DEV_ADMIN_AUTH_TOKEN,
        settings.DEV_DEVELOPER_AUTH_TOKEN,
    ):
        return _resolve_dev_user(token)
    if settings.KEYCLOAK_ENABLED:
        return await _resolve_keycloak_user(token)
    if settings.DEV_AUTH_ENABLED:
        raise InvalidToken(message="Invalid development token.")
    raise AuthenticationRequired(message="Authentication is not configured.")


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> CurrentUser:
    gateway_user = _user_from_gateway_headers(request)
    if gateway_user is not None:
        request.state.tenant_id = gateway_user.tenant_id
        request.state.user_id = gateway_user.user_id
        return gateway_user
    if not credentials:
        raise AuthenticationRequired(message="Authentication required.")
    user = await _authenticate_token(credentials.credentials)
    request.state.tenant_id = user.tenant_id
    request.state.user_id = user.user_id
    return user


async def get_current_user_optional(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> CurrentUser | None:
    gateway_user = _user_from_gateway_headers(request)
    if gateway_user is not None:
        request.state.tenant_id = gateway_user.tenant_id
        request.state.user_id = gateway_user.user_id
        return gateway_user
    if (
        get_settings().EDGE_AUTH_ENABLED
        and get_settings().GATEWAY_AUTH_SECRET
        and request.headers.get(GATEWAY_TRUST_HEADER) == get_settings().GATEWAY_AUTH_SECRET
    ):
        return None
    if not credentials:
        return None
    try:
        return await get_current_user(request, credentials)
    except Exception:
        return None


AuthRequired = Annotated[CurrentUser, Depends(get_current_user)]
AuthOptional = Annotated[CurrentUser | None, Depends(get_current_user_optional)]
