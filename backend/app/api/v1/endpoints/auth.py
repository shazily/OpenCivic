"""Authentication endpoints — config, dev login, OIDC, refresh, logout."""

from __future__ import annotations

import base64
import hashlib
import secrets
import uuid

import structlog
from fastapi import APIRouter, Query, Request, Response
from pydantic import BaseModel, Field

from app.api.v1.dependencies.auth import AuthRequired
from app.core.cache import cache_delete, cache_get, cache_set
from app.core.config import settings
from app.core.errors import AuthenticationRequired, InvalidToken
from app.core.security import revoke_token
from app.db.models import User
from app.db.session import AsyncReadSession, ReadSession, _ensure_engines, set_tenant_context
from app.services.auth.jwt_claims import decode_jwt_payload, extract_roles_and_staff_role
from app.services.auth.keycloak_client import KeycloakTokenClient
from app.services.auth.keycloak_session_index import (
    register_keycloak_refresh,
    unregister_keycloak_refresh,
)
from app.services.auth.refresh_service import RefreshService
from app.services.auth.user_resolver import resolve_user_from_claims

router = APIRouter()
refresh_service = RefreshService()
keycloak_client = KeycloakTokenClient()
logger = structlog.get_logger(__name__)


class DevLoginRequest(BaseModel):
    """Dev-only login to bootstrap refresh cookie."""

    role: str = Field(
        default="publisher",
        pattern=r"^(publisher|steward|admin|developer)$",
    )


class OidcCallbackRequest(BaseModel):
    """Authorization code returned by Keycloak to the portal callback."""

    code: str = Field(min_length=1)
    state: str = Field(min_length=1)
    redirect_uri: str = Field(min_length=1)


def _pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) for S256 PKCE."""
    code_verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


def _cookie_params() -> dict[str, object]:
    return {
        "httponly": True,
        "secure": settings.DEPLOYMENT_MODE == "cloud",
        "samesite": "strict",
        "max_age": settings.REFRESH_COOKIE_MAX_AGE_SECONDS,
        "path": "/api/v1/auth",
    }


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(settings.REFRESH_COOKIE_NAME, token, **_cookie_params())


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(settings.REFRESH_COOKIE_NAME, path="/api/v1/auth")


def _dev_access_token_for_role(role: str) -> tuple[str, uuid.UUID, list[str]]:
    if role == "steward":
        return (
            settings.DEV_STEWARD_AUTH_TOKEN,
            uuid.UUID(settings.DEV_STEWARD_USER_ID),
            ["data_steward"],
        )
    if role == "admin":
        return (
            settings.DEV_ADMIN_AUTH_TOKEN,
            uuid.UUID(settings.DEV_ADMIN_USER_ID),
            ["org_admin"],
        )
    if role == "developer":
        return (
            settings.DEV_DEVELOPER_AUTH_TOKEN,
            uuid.UUID(settings.DEV_DEVELOPER_USER_ID),
            ["developer"],
        )
    return (
        settings.DEV_AUTH_TOKEN,
        uuid.UUID(settings.DEV_USER_ID),
        ["data_publisher"],
    )


@router.get("/config")
async def auth_config() -> dict[str, object]:
    """Public auth configuration for the portal and developer console."""
    return {
        "data": {
            "dev_auth_enabled": settings.DEV_AUTH_ENABLED,
            "keycloak_enabled": settings.KEYCLOAK_ENABLED,
            "keycloak_url": settings.KEYCLOAK_URL if settings.KEYCLOAK_ENABLED else None,
            "keycloak_realm": settings.KEYCLOAK_REALM if settings.KEYCLOAK_ENABLED else None,
            "keycloak_client_id": (
                settings.KEYCLOAK_CLIENT_ID if settings.KEYCLOAK_ENABLED else None
            ),
            "refresh_cookie_name": settings.REFRESH_COOKIE_NAME,
        },
        "meta": {},
        "errors": [],
    }


@router.get("/mfa/status")
async def mfa_status(session: ReadSession, current_user: AuthRequired) -> dict:
    """Return MFA enrollment state for the authenticated user."""
    from sqlalchemy import select

    from app.services.auth.mfa_enforcement import MFA_REQUIRED_ROLES

    user = await session.scalar(select(User).where(User.id == current_user.user_id))
    mfa_enabled = bool(user.mfa_enabled) if user else False
    enrollment_required = settings.MFA_ENFORCEMENT_ENABLED and any(
        role in MFA_REQUIRED_ROLES for role in current_user.roles
    )
    return {
        "data": {
            "mfa_enabled": mfa_enabled,
            "enforcement_enabled": settings.MFA_ENFORCEMENT_ENABLED,
            "enrollment_required": enrollment_required,
            "provider": "keycloak" if settings.KEYCLOAK_ENABLED else "local",
            "keycloak_enabled": settings.KEYCLOAK_ENABLED,
        },
        "meta": {},
        "errors": [],
    }


@router.get("/oidc/login")
async def oidc_login(redirect_uri: str = Query(..., min_length=1)) -> dict[str, object]:
    """
    Start Keycloak OIDC sign-in with PKCE.
    Stores code_verifier in Valkey keyed by state for the callback exchange.
    """
    if not settings.KEYCLOAK_ENABLED:
        raise AuthenticationRequired(message="Keycloak sign-in is not enabled.")
    code_verifier, code_challenge = _pkce_pair()
    state = secrets.token_urlsafe(32)
    await cache_set(f"oidc:state:{state}", code_verifier, ttl_seconds=600)
    authorization_url = keycloak_client.authorize_url(
        redirect_uri=redirect_uri,
        state=state,
        code_challenge=code_challenge,
    )
    return {
        "data": {
            "authorization_url": authorization_url,
            "state": state,
        },
        "meta": {},
        "errors": [],
    }


@router.post("/oidc/callback")
async def oidc_callback(body: OidcCallbackRequest, response: Response) -> dict[str, object]:
    """Exchange Keycloak authorization code for tokens; refresh token in httpOnly cookie."""
    if not settings.KEYCLOAK_ENABLED:
        raise AuthenticationRequired(message="Keycloak sign-in is not enabled.")
    code_verifier = await cache_get(f"oidc:state:{body.state}")
    if not code_verifier:
        raise InvalidToken(message="OIDC state expired or invalid.", code="INVALID_OIDC_STATE")
    await cache_delete(f"oidc:state:{body.state}")

    tokens = await keycloak_client.exchange_authorization_code(
        code=body.code,
        redirect_uri=body.redirect_uri,
        code_verifier=code_verifier,
    )
    refresh_token = tokens.get("refresh_token")
    access_token = str(tokens["access_token"])
    if isinstance(refresh_token, str) and refresh_token:
        _set_refresh_cookie(response, refresh_token)
        claims = decode_jwt_payload(access_token)
        if claims:
            try:
                _ensure_engines()
                tenant_raw = claims.get("tenant_id", settings.DEV_TENANT_ID)
                async with AsyncReadSession() as read_session:
                    await set_tenant_context(read_session, uuid.UUID(str(tenant_raw)))
                    user = await resolve_user_from_claims(read_session, claims)
                    await register_keycloak_refresh(user.user_id, refresh_token)
            except Exception:
                logger.warning("keycloak_refresh_index_skipped")
    roles, staff_role = extract_roles_and_staff_role(access_token)
    return {
        "data": {
            "access_token": access_token,
            "token_type": tokens.get("token_type", "Bearer"),
            "expires_in": tokens.get("expires_in", 900),
            "roles": roles,
            "staff_role": staff_role,
        },
        "meta": {},
        "errors": [],
    }


@router.post("/dev-login")
async def dev_login(body: DevLoginRequest, response: Response) -> dict[str, object]:
    """
    Dev-only: issue access token in body and refresh token in httpOnly cookie.
    Disabled when DEV_AUTH_ENABLED is false.
    """
    if not settings.DEV_AUTH_ENABLED:
        raise AuthenticationRequired(message="Development login is disabled.")
    access_token, user_id, roles = _dev_access_token_for_role(body.role)
    refresh_token, _family = await refresh_service.create_session(
        user_id=user_id,
        tenant_id=uuid.UUID(settings.DEV_TENANT_ID),
        roles=roles,
    )
    _set_refresh_cookie(response, refresh_token)
    return {
        "data": {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 900,
            "user_id": str(user_id),
            "roles": roles,
        },
        "meta": {},
        "errors": [],
    }


@router.post("/refresh")
async def refresh_session(request: Request, response: Response) -> dict[str, object]:
    """
    Rotate refresh token from httpOnly cookie and return a new access token.
    Keycloak mode exchanges cookie token with Keycloak; dev mode rotates Valkey session.
    """
    refresh_token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise InvalidToken(message="Refresh cookie is missing.", code="MISSING_REFRESH")

    if settings.KEYCLOAK_ENABLED and not settings.DEV_AUTH_ENABLED:
        tokens = await keycloak_client.refresh_tokens(refresh_token)
        new_refresh = tokens.get("refresh_token", refresh_token)
        _set_refresh_cookie(response, new_refresh)
        return {
            "data": {
                "access_token": tokens["access_token"],
                "token_type": tokens.get("token_type", "Bearer"),
                "expires_in": tokens.get("expires_in", 900),
            },
            "meta": {},
            "errors": [],
        }

    new_refresh, session = await refresh_service.rotate(refresh_token)
    _set_refresh_cookie(response, new_refresh)
    if str(session.user_id) == settings.DEV_STEWARD_USER_ID:
        access_token = settings.DEV_STEWARD_AUTH_TOKEN
    elif str(session.user_id) == settings.DEV_ADMIN_USER_ID:
        access_token = settings.DEV_ADMIN_AUTH_TOKEN
    elif str(session.user_id) == settings.DEV_DEVELOPER_USER_ID:
        access_token = settings.DEV_DEVELOPER_AUTH_TOKEN
    else:
        access_token = settings.DEV_AUTH_TOKEN
    return {
        "data": {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 900,
            "user_id": str(session.user_id),
            "roles": session.roles,
        },
        "meta": {},
        "errors": [],
    }


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    current_user: AuthRequired,
) -> dict[str, object]:
    """Clear refresh cookie, revoke refresh family, and blocklist access token jti."""
    refresh_token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if refresh_token:
        if settings.KEYCLOAK_ENABLED and not settings.DEV_AUTH_ENABLED:
            await keycloak_client.revoke_refresh_token(refresh_token)
            await unregister_keycloak_refresh(current_user.user_id, refresh_token)
        else:
            try:
                session = await refresh_service.load_session(refresh_token)
                await refresh_service.revoke_family(session.family_id)
            except InvalidToken:
                pass

    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1]
        if settings.KEYCLOAK_ENABLED:
            from jose import jwt as jose_jwt

            try:
                claims = jose_jwt.get_unverified_claims(token)
                jti = claims.get("jti")
                if isinstance(jti, str) and jti:
                    await revoke_token(jti, ttl_seconds=900)
            except Exception:
                logger.debug("logout_jti_blocklist_skipped")

    _clear_refresh_cookie(response)
    return {
        "data": {"logged_out": True, "user_id": str(current_user.user_id)},
        "meta": {},
        "errors": [],
    }
