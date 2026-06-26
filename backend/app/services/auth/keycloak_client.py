"""Keycloak token endpoint client for refresh, logout, and OIDC code exchange."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx
import structlog

from app.core.config import settings
from app.core.errors import AuthenticationRequired, InvalidToken

logger = structlog.get_logger(__name__)


class KeycloakTokenClient:
    """Exchange and refresh tokens with Keycloak OpenID Connect."""

    def realm_base(self) -> str:
        return f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}"

    def token_url(self) -> str:
        return f"{self.realm_base()}/protocol/openid-connect/token"

    def logout_url(self) -> str:
        return f"{self.realm_base()}/protocol/openid-connect/logout"

    def authorize_url(self, *, redirect_uri: str, state: str, code_challenge: str) -> str:
        """Build an authorization URL with PKCE (S256)."""
        params = {
            "client_id": settings.KEYCLOAK_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid profile email",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{self.realm_base()}/protocol/openid-connect/auth?{urlencode(params)}"

    async def exchange_authorization_code(
        self,
        *,
        code: str,
        redirect_uri: str,
        code_verifier: str,
    ) -> dict[str, Any]:
        """Exchange an authorization code for access and refresh tokens."""
        if not settings.KEYCLOAK_CLIENT_SECRET:
            raise AuthenticationRequired(
                message="Keycloak client secret is not configured.",
                code="KEYCLOAK_NOT_CONFIGURED",
            )
        data = {
            "grant_type": "authorization_code",
            "client_id": settings.KEYCLOAK_CLIENT_ID,
            "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(self.token_url(), data=data, timeout=15.0)
        if response.status_code != 200:
            logger.warning("keycloak_code_exchange_failed", status=response.status_code)
            raise InvalidToken(message="Failed to complete sign-in with identity provider.")
        return response.json()

    async def refresh_tokens(self, refresh_token: str) -> dict[str, Any]:
        """Exchange a refresh token for new access + refresh tokens."""
        if not settings.KEYCLOAK_CLIENT_SECRET:
            raise AuthenticationRequired(
                message="Keycloak client secret is not configured.",
                code="KEYCLOAK_NOT_CONFIGURED",
            )
        data = {
            "grant_type": "refresh_token",
            "client_id": settings.KEYCLOAK_CLIENT_ID,
            "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
            "refresh_token": refresh_token,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(self.token_url(), data=data, timeout=15.0)
        if response.status_code != 200:
            logger.warning("keycloak_refresh_failed", status=response.status_code)
            raise InvalidToken(message="Failed to refresh session with identity provider.")
        return response.json()

    async def revoke_refresh_token(self, refresh_token: str) -> None:
        """Revoke refresh token at Keycloak (best-effort)."""
        if not settings.KEYCLOAK_CLIENT_SECRET:
            return
        data = {
            "client_id": settings.KEYCLOAK_CLIENT_ID,
            "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
            "refresh_token": refresh_token,
        }
        try:
            async with httpx.AsyncClient() as client:
                await client.post(self.logout_url(), data=data, timeout=10.0)
        except Exception as exc:
            logger.warning("keycloak_logout_failed", error=str(exc))
