"""Keycloak OIDC login flow tests."""

import os
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_oidc_login_returns_authorization_url(client: AsyncClient) -> None:
    with patch("app.api.v1.endpoints.auth.settings.KEYCLOAK_ENABLED", True):
        with patch("app.api.v1.endpoints.auth.cache_set", new_callable=AsyncMock):
            response = await client.get(
                "/api/v1/auth/oidc/login",
                params={"redirect_uri": "http://127.0.0.1:3100/login/callback"},
            )
    assert response.status_code == 200
    body = response.json()["data"]
    assert "authorization_url" in body
    assert "state" in body
    assert "protocol/openid-connect/auth" in body["authorization_url"]


@pytest.mark.asyncio
async def test_oidc_login_disabled_when_keycloak_off(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/auth/oidc/login",
        params={"redirect_uri": "http://127.0.0.1:3100/login/callback"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_oidc_callback_exchanges_code_for_tokens(client: AsyncClient) -> None:
    with patch("app.api.v1.endpoints.auth.settings.KEYCLOAK_ENABLED", True):
        with patch("app.api.v1.endpoints.auth.cache_get", new_callable=AsyncMock, return_value="verifier"):
            with patch("app.api.v1.endpoints.auth.cache_delete", new_callable=AsyncMock):
                with patch(
                    "app.api.v1.endpoints.auth.keycloak_client.exchange_authorization_code",
                    new_callable=AsyncMock,
                    return_value={
                        "access_token": os.environ["DEV_AUTH_TOKEN"],
                        "refresh_token": "refresh-test",
                        "token_type": "Bearer",
                        "expires_in": 900,
                    },
                ):
                    response = await client.post(
                        "/api/v1/auth/oidc/callback",
                        json={
                            "code": "auth-code",
                            "state": "state-123",
                            "redirect_uri": "http://127.0.0.1:3100/login/callback",
                        },
                    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["access_token"] == os.environ["DEV_AUTH_TOKEN"]
    assert "staff_role" in body
    assert "opencivic_refresh" in response.cookies
