"""Celery queue depth probes via Valkey broker lists and optional Flower workers API."""

from __future__ import annotations

from dataclasses import dataclass

import httpx
import structlog

from app.core.cache import get_cache
from app.core.config import settings

logger = structlog.get_logger(__name__)

CELERY_QUEUE_NAMES = (
    "critical",
    "ingest",
    "refresh",
    "ai",
    "notifications",
    "maintenance",
)


@dataclass(frozen=True)
class QueueSnapshot:
    """Single queue depth reading."""

    name: str
    depth: int
    status: str


def depth_trend_stub(depth: int) -> list[int]:
    """Return a three-point depth trend stub for admin sparklines."""
    if depth <= 0:
        return [0, 0, 0]
    return [max(0, int(depth * 0.6)), max(0, int(depth * 0.8)), depth]


def _depth_status(depth: int) -> str:
    if depth >= 1000:
        return "backlogged"
    if depth > 0:
        return "active"
    return "idle"


def _flower_auth() -> tuple[str, str] | None:
    if settings.FLOWER_USER and settings.FLOWER_PASSWORD:
        return (settings.FLOWER_USER, settings.FLOWER_PASSWORD)
    return None


async def _flower_worker_count() -> int | None:
    """Best-effort active worker count from Flower HTTP API."""
    flower_url = settings.FLOWER_URL.strip()
    if not flower_url:
        return None
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{flower_url.rstrip('/')}/api/workers",
                auth=_flower_auth(),
                timeout=5.0,
            )
        if response.status_code != 200:
            return None
        payload = response.json()
        if isinstance(payload, dict):
            return len(payload)
        return None
    except Exception as exc:
        logger.debug("flower_workers_probe_failed", error=str(exc))
        return None


async def _flower_queue_depths() -> dict[str, int] | None:
    """Read queue depths from Flower broker inspect API when available."""
    flower_url = settings.FLOWER_URL.strip()
    if not flower_url:
        return None
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{flower_url.rstrip('/')}/api/queues/length",
                auth=_flower_auth(),
                timeout=5.0,
            )
        if response.status_code != 200:
            return None
        payload = response.json()
        depths: dict[str, int] = {}
        if isinstance(payload, dict):
            for name in CELERY_QUEUE_NAMES:
                raw = payload.get(name)
                if isinstance(raw, int):
                    depths[name] = raw
                elif isinstance(raw, dict) and isinstance(raw.get("messages"), int):
                    depths[name] = int(raw["messages"])
        if depths:
            return depths
        return None
    except Exception as exc:
        logger.debug("flower_queue_probe_failed", error=str(exc))
        return None


async def _valkey_queue_depths() -> dict[str, int]:
    """Read Celery queue list lengths from the Valkey broker."""
    client = await get_cache()
    depths: dict[str, int] = {}
    for name in CELERY_QUEUE_NAMES:
        depths[name] = int(await client.llen(name))
    return depths


def _snapshots_from_depths(depths: dict[str, int]) -> list[QueueSnapshot]:
    return [
        QueueSnapshot(name=name, depth=depths.get(name, 0), status=_depth_status(depths.get(name, 0)))
        for name in CELERY_QUEUE_NAMES
    ]


async def get_celery_queue_snapshots() -> tuple[list[QueueSnapshot], str, int | None]:
    """
  Probe queue depths with fallback chain: Flower broker → Valkey LLEN → placeholder.

    Returns (queues, source, worker_count).
    """
    worker_count = await _flower_worker_count()

    flower_depths = await _flower_queue_depths()
    if flower_depths is not None:
        snapshots = _snapshots_from_depths(flower_depths)
        source = "flower+workers" if worker_count is not None else "flower"
        return snapshots, source, worker_count

    try:
        valkey_depths = await _valkey_queue_depths()
        snapshots = _snapshots_from_depths(valkey_depths)
        source = "valkey+flower" if worker_count is not None else "valkey"
        return snapshots, source, worker_count
    except Exception as exc:
        logger.warning("celery_queue_probe_failed", error=str(exc))
        placeholders = [
            QueueSnapshot(name=name, depth=0, status="unknown") for name in CELERY_QUEUE_NAMES
        ]
        return placeholders, "placeholder", worker_count
