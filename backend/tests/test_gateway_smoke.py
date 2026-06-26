"""Gateway path smoke — skipped unless OPENCIVIC_GATEWAY_URL is reachable."""

import os

import httpx
import pytest

GATEWAY_BASE = os.environ.get("OPENCIVIC_GATEWAY_URL", "http://127.0.0.1:8080")


def _gateway_reachable() -> bool:
    try:
        response = httpx.get(f"{GATEWAY_BASE.rstrip('/')}/api/v1/health/live", timeout=3.0)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


@pytest.mark.gateway
@pytest.mark.skipif(not _gateway_reachable(), reason="gateway not reachable")
def test_health_live_via_gateway() -> None:
    response = httpx.get(f"{GATEWAY_BASE.rstrip('/')}/api/v1/health/live", timeout=5.0)
    assert response.status_code == 200
    assert response.json().get("status") == "ok"


@pytest.mark.gateway
@pytest.mark.skipif(not _gateway_reachable(), reason="gateway not reachable")
def test_rate_limit_headers_present() -> None:
    response = httpx.get(f"{GATEWAY_BASE.rstrip('/')}/api/v1/health/live", timeout=5.0)
    assert response.status_code == 200
    assert response.headers.get("X-RateLimit-Limit") is not None
