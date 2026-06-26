"""Live pgBackRest verification — skipped unless backup profile is running."""

import os

import pytest

from app.core.config import get_settings
from app.workers.tasks.tasks import verify_backup_integrity


@pytest.mark.live
@pytest.mark.skipif(
    os.environ.get("PGBACKREST_ENABLED", "").lower() not in {"1", "true", "yes"},
    reason="PGBACKREST_ENABLED is not set",
)
def test_pgbackrest_verify_task_records_status(event_loop, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run verify_backup_integrity when pgBackRest sidecar is configured."""
    get_settings.cache_clear()
    result = verify_backup_integrity()
    assert result["status"] in {"ok", "failed", "skipped"}
    if result["status"] == "ok":
        from app.services.platform.backup_status import get_backup_status

        status = event_loop.run_until_complete(get_backup_status())
        assert status.get("verified_at")
