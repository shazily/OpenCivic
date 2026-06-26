"""Extended backup verification task tests."""

import asyncio
import json
from unittest.mock import MagicMock

import pytest

from app.services.platform.backup_status import BACKUP_STATUS_KEY


@pytest.mark.asyncio
async def test_verify_backup_integrity_writes_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    stored: dict[str, str] = {}

    async def fake_cache_set(key: str, value: str, ttl_seconds: int = 0) -> None:
        stored[key] = value

    monkeypatch.setattr("app.core.cache.cache_set", fake_cache_set)
    monkeypatch.setattr("app.core.config.settings.PGBACKREST_ENABLED", False)

    from app.workers.tasks.tasks import verify_backup_integrity

    result = verify_backup_integrity()
    assert result["status"] == "ok"
    assert "verified_at" in result
    assert BACKUP_STATUS_KEY in stored


def test_verify_backup_integrity_runs_pgbackrest(
    monkeypatch: pytest.MonkeyPatch,
    event_loop: asyncio.AbstractEventLoop,
) -> None:
    import asyncio

    stored: dict[str, str] = {}

    async def fake_cache_set(key: str, value: str, ttl_seconds: int = 0) -> None:
        stored[key] = value

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "verify successful"
    mock_result.stderr = ""

    monkeypatch.setattr("app.core.cache.cache_set", fake_cache_set)
    monkeypatch.setattr("app.core.config.settings.PGBACKREST_ENABLED", True)
    monkeypatch.setattr("app.core.config.settings.PGBACKREST_STANZA", "opencivic")
    monkeypatch.setattr("app.core.config.settings.PGBACKREST_COMMAND", "pgbackrest")
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: mock_result)

    def fake_run_async(coro: object) -> object:
        return event_loop.run_until_complete(coro)  # type: ignore[arg-type]

    monkeypatch.setattr("app.workers.async_runner.run_async", fake_run_async)

    from app.workers.tasks.tasks import verify_backup_integrity

    result = verify_backup_integrity()
    assert result["status"] == "ok"
    assert "verify successful" in result["message"]
    assert BACKUP_STATUS_KEY in stored
