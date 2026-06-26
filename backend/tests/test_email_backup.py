"""Email and backup status service tests."""

import json

import pytest

from app.services.notifications.email_service import EmailService
from app.services.platform.backup_status import BACKUP_STATUS_KEY, get_backup_status


def test_email_service_skips_when_smtp_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.notifications.email_service.settings.SMTP_HOST", "")
    result = EmailService.send_sync(
        to="steward@test.local",
        subject="Test",
        body_html="<p>Hello</p>",
    )
    assert result["status"] == "skipped"


@pytest.mark.asyncio
async def test_backup_status_not_configured_in_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.cache import cache_get

    async def _empty(_key: str) -> str | None:
        return None

    monkeypatch.setattr("app.services.platform.backup_status.cache_get", _empty)
    monkeypatch.setattr("app.services.platform.backup_status.settings.DEPLOYMENT_MODE", "selfhosted")
    status = await get_backup_status()
    assert status["status"] == "not_configured"


@pytest.mark.asyncio
async def test_backup_status_reads_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = json.dumps(
        {
            "status": "ok",
            "verified_at": "2026-06-16T12:00:00+00:00",
            "message": "verified",
        }
    )

    async def _cached(key: str) -> str | None:
        assert key == BACKUP_STATUS_KEY
        return payload

    monkeypatch.setattr("app.services.platform.backup_status.cache_get", _cached)
    status = await get_backup_status()
    assert status["status"] == "ok"
    assert status["verified_at"] == "2026-06-16T12:00:00+00:00"
