"""Derive connector sync history entries from connector state (v1 stub)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.db.models import Connector


def build_connector_sync_history(connector: Connector, *, limit: int = 10) -> list[dict[str, object]]:
    """Return recent sync history derived from connector timestamps and status."""
    entries: list[dict[str, object]] = []
    now = datetime.now(UTC)

    if connector.last_sync_at is not None:
        entries.append(
            {
                "occurred_at": connector.last_sync_at.isoformat(),
                "status": "error" if connector.status == "error" else "success",
                "failure_count": connector.failure_count,
                "circuit_state": connector.circuit_state,
                "source": "last_sync",
            }
        )

    if connector.next_sync_at is not None and connector.next_sync_at > now:
        entries.append(
            {
                "occurred_at": connector.next_sync_at.isoformat(),
                "status": "scheduled",
                "failure_count": connector.failure_count,
                "circuit_state": connector.circuit_state,
                "source": "next_sync",
            }
        )

    if connector.failure_count > 0 and connector.status == "error":
        estimated = (connector.last_sync_at or now) - timedelta(hours=1)
        entries.append(
            {
                "occurred_at": estimated.isoformat(),
                "status": "error",
                "failure_count": connector.failure_count,
                "circuit_state": connector.circuit_state,
                "source": "failure_stub",
            }
        )

    entries.sort(key=lambda item: str(item["occurred_at"]), reverse=True)
    return entries[:limit]
