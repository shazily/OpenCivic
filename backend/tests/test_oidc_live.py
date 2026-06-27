"""Live Keycloak OIDC — skipped when Keycloak is unreachable."""

import httpx
import pytest

from app.core.config import settings


def _keycloak_reachable() -> bool:
    base = settings.KEYCLOAK_URL.rstrip("/")
    try:
        response = httpx.get(f"{base}/health/ready", timeout=5.0)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


@pytest.mark.live
@pytest.mark.pilot
@pytest.mark.skipif(not settings.KEYCLOAK_ENABLED, reason="Keycloak disabled")
@pytest.mark.skipif(not _keycloak_reachable(), reason="Keycloak not reachable")
def test_oidc_login_url_shape() -> None:
    from app.services.auth.keycloak_client import KeycloakTokenClient

    client = KeycloakTokenClient()
    url = client.authorize_url(
        redirect_uri="http://127.0.0.1:3100/login/callback",
        state="test-state",
        code_challenge="test-challenge",
    )
    assert settings.KEYCLOAK_REALM in url
    assert settings.keycloak_public_url.rstrip("/") in url
    assert "client_id=" in url
    assert "code_challenge=" in url


@pytest.mark.live
@pytest.mark.pilot
@pytest.mark.skipif(not settings.KEYCLOAK_ENABLED, reason="Keycloak disabled")
@pytest.mark.skipif(not _keycloak_reachable(), reason="Keycloak not reachable")
def test_keycloak_token_endpoint_reachable() -> None:
    base = settings.KEYCLOAK_URL.rstrip("/")
    url = f"{base}/realms/{settings.KEYCLOAK_REALM}/.well-known/openid-configuration"
    response = httpx.get(url, timeout=10.0)
    assert response.status_code == 200
    body = response.json()
    assert "authorization_endpoint" in body
    assert "token_endpoint" in body
