"""Gateway forward-auth decision logic and trusted-header auth."""

import os
import uuid

import pytest
from httpx import AsyncClient

from app.services.auth.gateway_auth import (
    GatewayAuthMode,
    GatewayIdentity,
    build_gateway_trust_headers,
    classify_gateway_path,
    evaluate_gateway_auth,
)


def test_classify_public_health_path() -> None:
    assert classify_gateway_path("GET", "/api/v1/health/live") == GatewayAuthMode.PUBLIC


def test_classify_auth_paths_public() -> None:
    assert classify_gateway_path("POST", "/api/v1/auth/dev-login") == GatewayAuthMode.PUBLIC


def test_classify_datasets_optional() -> None:
    assert classify_gateway_path("GET", "/api/v1/datasets") == GatewayAuthMode.OPTIONAL


def test_classify_admin_required() -> None:
    assert classify_gateway_path("GET", "/api/v1/admin/backup/status") == GatewayAuthMode.REQUIRED


@pytest.mark.asyncio
async def test_evaluate_public_path_allows_anonymous() -> None:
    status, headers = await evaluate_gateway_auth("GET", "/api/v1/health/live", None, None)
    assert status == 200
    assert "X-OpenCivic-Gateway-Trust" in headers
    assert "X-OpenCivic-User-Id" not in headers


@pytest.mark.asyncio
async def test_evaluate_protected_path_rejects_without_credentials() -> None:
    status, headers = await evaluate_gateway_auth("GET", "/api/v1/users/me", None, None)
    assert status == 401
    assert headers == {}


@pytest.mark.asyncio
async def test_evaluate_protected_path_accepts_dev_jwt() -> None:
    token = os.environ["DEV_AUTH_TOKEN"]
    status, headers = await evaluate_gateway_auth(
        "GET",
        "/api/v1/users/me",
        f"Bearer {token}",
        None,
    )
    assert status == 200
    assert headers["X-OpenCivic-User-Id"] == os.environ["DEV_USER_ID"]
    assert headers["X-OpenCivic-Tenant-Id"] == os.environ["DEV_TENANT_ID"]
    assert headers["X-OpenCivic-Auth-Type"] == "jwt"


@pytest.mark.asyncio
async def test_gateway_auth_endpoint(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/internal/gateway-auth",
        headers={
            "X-Forwarded-Uri": "/api/v1/notifications",
            "X-Forwarded-Method": "GET",
        },
    )
    assert response.status_code == 401

    response = await client.get(
        "/api/v1/internal/gateway-auth",
        headers={
            "Authorization": f"Bearer {os.environ['DEV_AUTH_TOKEN']}",
            "X-Forwarded-Uri": "/api/v1/notifications",
            "X-Forwarded-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["X-OpenCivic-Auth-Type"] == "jwt"


@pytest.mark.asyncio
async def test_trusted_gateway_headers_used_by_api(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("EDGE_AUTH_ENABLED", "true")
    monkeypatch.setenv("GATEWAY_AUTH_SECRET", "test-gateway-secret")
    get_settings.cache_clear()

    user_id = os.environ["DEV_USER_ID"]
    tenant_id = os.environ["DEV_TENANT_ID"]
    headers = build_gateway_trust_headers(
        GatewayIdentity(
            user_id=uuid.UUID(user_id),
            tenant_id=uuid.UUID(tenant_id),
            roles=["data_publisher"],
            auth_type="jwt",
        )
    )
    headers["X-OpenCivic-Gateway-Trust"] = "test-gateway-secret"

    response = await client.get("/api/v1/users/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["data"]["id"] == user_id

    spoofed = dict(headers)
    spoofed["X-OpenCivic-Gateway-Trust"] = "wrong-secret"
    response = await client.get("/api/v1/users/me", headers=spoofed)
    assert response.status_code == 401

    get_settings.cache_clear()
