"""Backup verification status for IT admin console."""

from __future__ import annotations

import json

from app.core.cache import cache_get
from app.core.config import settings

BACKUP_STATUS_KEY = "platform:backup:last_verification"


async def get_backup_status() -> dict[str, str | None]:
    """Return last backup verification snapshot from Valkey, or not_configured."""
    raw = await cache_get(BACKUP_STATUS_KEY)
    if raw:
        try:
            payload = json.loads(raw)
            return {
                "status": str(payload.get("status", "unknown")),
                "verified_at": payload.get("verified_at"),
                "message": payload.get("message"),
            }
        except json.JSONDecodeError:
            pass
    if settings.DEPLOYMENT_MODE == "cloud":
        return {
            "status": "pending",
            "verified_at": None,
            "message": "Managed backup expected; verification job not run yet.",
        }
    return {
        "status": "not_configured",
        "verified_at": None,
        "message": "pgBackRest not configured in dev compose.",
    }
