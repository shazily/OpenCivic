"""Unit tests for connector sync history stub builder."""

from datetime import UTC, datetime
from types import SimpleNamespace

from app.services.connectors.connector_sync_history import build_connector_sync_history


def test_build_connector_sync_history_includes_last_sync() -> None:
    connector = SimpleNamespace(
        status="active",
        circuit_state="closed",
        failure_count=0,
        last_sync_at=datetime(2026, 6, 10, 12, 0, tzinfo=UTC),
        next_sync_at=None,
    )
    history = build_connector_sync_history(connector)
    assert len(history) >= 1
    assert history[0]["status"] == "success"
    assert history[0]["source"] == "last_sync"


def test_build_connector_sync_history_includes_failure_stub() -> None:
    connector = SimpleNamespace(
        status="error",
        circuit_state="open",
        failure_count=3,
        last_sync_at=datetime(2026, 6, 10, 12, 0, tzinfo=UTC),
        next_sync_at=None,
    )
    history = build_connector_sync_history(connector)
    statuses = {item["status"] for item in history}
    assert "error" in statuses
