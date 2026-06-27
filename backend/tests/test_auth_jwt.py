"""JWT validation and refresh cookie integration tests."""

from __future__ import annotations

import base64
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from jose import jwt as jose_jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import get_settings
from app.core.security import jwt_validator


def _int_to_base64url(value: int) -> str:
    length = (value.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(value.to_bytes(length, "big")).decode().rstrip("=")


@pytest.fixture
def rsa_keypair() -> tuple[bytes, dict]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_numbers = key.public_key().public_numbers()
    jwk = {
        "kty": "RSA",
        "kid": "test-key-id",
        "use": "sig",
        "alg": "RS256",
        "n": _int_to_base64url(public_numbers.n),
        "e": _int_to_base64url(public_numbers.e),
    }
    return private_pem, {"keys": [jwk]}


def _sign_token(private_pem: bytes, claims: dict) -> str:
    return jose_jwt.encode(claims, private_pem, algorithm="RS256", headers={"kid": "test-key-id"})


@pytest.mark.asyncio
async def test_jwt_validator_accepts_valid_token(
    monkeypatch: pytest.MonkeyPatch,
    rsa_keypair: tuple[bytes, dict],
    db_session,
) -> None:
    private_pem, jwks = rsa_keypair
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000002")

    async def fake_jwks(_realm: str) -> dict:
        return jwks

    async def noop_blocklist(_jti: str) -> None:
        return None

    monkeypatch.setattr(jwt_validator, "get_jwks", fake_jwks)
    monkeypatch.setattr("app.core.security._check_token_blocklist", noop_blocklist)

    token = _sign_token(
        private_pem,
        {
            "sub": str(user_id),
            "email": "publisher@test.local",
            "tenant_id": str(tenant_id),
            "realm_access": {"roles": ["data_publisher"]},
            "exp": datetime.now(UTC) + timedelta(minutes=5),
            "jti": "test-jti-valid",
        },
    )

    claims = await jwt_validator.validate_token(token, "dev")
    assert claims["email"] == "publisher@test.local"


@pytest.mark.asyncio
async def test_refresh_cookie_flow_dev_login(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/dev-login", json={"role": "publisher"})
    assert response.status_code == 200
    assert "access_token" in response.json()["data"]
    assert settings_cookie_present(response)


@pytest.mark.asyncio
async def test_refresh_rotates_cookie(client: AsyncClient) -> None:
    login = await client.post("/api/v1/auth/dev-login", json={"role": "publisher"})
    cookies = login.cookies
    refreshed = await client.post("/api/v1/auth/refresh", cookies=cookies)
    assert refreshed.status_code == 200
    assert refreshed.json()["data"]["access_token"]
    assert settings_cookie_present(refreshed)


@pytest.mark.asyncio
async def test_logout_clears_refresh_cookie(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    login = await client.post("/api/v1/auth/dev-login", json={"role": "publisher"})
    logout = await client.post("/api/v1/auth/logout", headers=auth_headers, cookies=login.cookies)
    assert logout.status_code == 200
    assert logout.json()["data"]["logged_out"] is True


def settings_cookie_present(response) -> bool:
    from app.core.config import settings

    return settings.REFRESH_COOKIE_NAME in response.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_keycloak_jwt_protected_endpoint(
    monkeypatch: pytest.MonkeyPatch,
    rsa_keypair: tuple[bytes, dict],
    client: AsyncClient,
    db_session,
) -> None:
    private_pem, jwks = rsa_keypair
    tenant_id = "00000000-0000-0000-0000-000000000001"

    get_settings.cache_clear()
    monkeypatch.setenv("KEYCLOAK_ENABLED", "true")
    monkeypatch.setenv("DEV_AUTH_ENABLED", "false")
    get_settings.cache_clear()

    async def fake_jwks(_realm: str) -> dict:
        return jwks

    async def noop_blocklist(_jti: str) -> None:
        return None

    monkeypatch.setattr(jwt_validator, "get_jwks", fake_jwks)
    monkeypatch.setattr("app.core.security._check_token_blocklist", noop_blocklist)

    token = _sign_token(
        private_pem,
        {
            "sub": "kc-user-1",
            "email": "publisher@test.local",
            "tenant_id": tenant_id,
            "realm_access": {"roles": ["data_publisher"]},
            "exp": datetime.now(UTC) + timedelta(minutes=5),
            "jti": "kc-jti-1",
        },
    )

    from app.core.config import get_settings as gs

    gs.cache_clear()
    response = await client.get(
        "/api/v1/datasets/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    monkeypatch.setenv("DEV_AUTH_ENABLED", "true")
    monkeypatch.setenv("KEYCLOAK_ENABLED", "false")
    get_settings.cache_clear()
