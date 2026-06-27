"""Live tusd reachability — skipped when tusd is not running."""

import httpx
import pytest

from app.core.config import settings


def _tusd_reachable() -> bool:
    base = settings.TUS_INTERNAL_URL.rstrip("/")
    try:
        response = httpx.get(f"{base}/", timeout=3.0, follow_redirects=True)
        return response.status_code < 500
    except httpx.HTTPError:
        return False


@pytest.mark.live
@pytest.mark.skipif(not _tusd_reachable(), reason="tusd not reachable")
def test_tusd_endpoint_reachable() -> None:
    base = settings.TUS_INTERNAL_URL.rstrip("/")
    response = httpx.get(f"{base}/", timeout=5.0, follow_redirects=True)
    assert response.status_code < 500
