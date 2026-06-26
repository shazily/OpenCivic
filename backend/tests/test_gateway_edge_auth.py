"""Live gateway edge-auth tests — require nginx + APISIX + EDGE_AUTH_ENABLED."""

import os

import httpx
import pytest

GATEWAY_BASE = os.environ.get("OPENCIVIC_GATEWAY_URL", "http://127.0.0.1:8080")
DEV_TOKEN = os.environ.get("DEV_AUTH_TOKEN", "dev-local-token-change-me")


def _gateway_reachable() -> bool:
    try:
        response = httpx.get(f"{GATEWAY_BASE.rstrip('/')}/api/v1/health/live", timeout=3.0)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


@pytest.mark.gateway
@pytest.mark.skipif(not _gateway_reachable(), reason="gateway not reachable")
def test_protected_route_rejects_anonymous_via_gateway() -> None:
    response = httpx.get(
        f"{GATEWAY_BASE.rstrip('/')}/api/v1/users/me",
        timeout=5.0,
    )
    assert response.status_code == 401


@pytest.mark.gateway
@pytest.mark.skipif(not _gateway_reachable(), reason="gateway not reachable")
def test_protected_route_accepts_dev_jwt_via_gateway() -> None:
    response = httpx.get(
        f"{GATEWAY_BASE.rstrip('/')}/api/v1/users/me",
        headers={"Authorization": f"Bearer {DEV_TOKEN}"},
        timeout=5.0,
    )
    assert response.status_code == 200
    assert response.json()["data"]["email"] == "publisher@test.local"


@pytest.mark.gateway
@pytest.mark.skipif(not _gateway_reachable(), reason="gateway not reachable")
def test_public_datasets_without_auth_via_gateway() -> None:
    response = httpx.get(
        f"{GATEWAY_BASE.rstrip('/')}/api/v1/datasets/",
        timeout=5.0,
        follow_redirects=True,
    )
    assert response.status_code == 200
