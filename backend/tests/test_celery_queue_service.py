"""Celery queue snapshot service."""

from unittest.mock import AsyncMock

import pytest

from app.services.platform.celery_queue_service import get_celery_queue_snapshots


@pytest.mark.asyncio
async def test_get_celery_queue_snapshots_falls_back_to_valkey(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = AsyncMock()
    mock_client.llen = AsyncMock(side_effect=[1, 0, 0, 0, 0, 0])

    async def fake_get_cache() -> AsyncMock:
        return mock_client

    async def fake_flower_depths() -> None:
        return None

    async def fake_flower_workers() -> None:
        return None

    monkeypatch.setattr(
        "app.services.platform.celery_queue_service.get_cache",
        fake_get_cache,
    )
    monkeypatch.setattr(
        "app.services.platform.celery_queue_service._flower_queue_depths",
        fake_flower_depths,
    )
    monkeypatch.setattr(
        "app.services.platform.celery_queue_service._flower_worker_count",
        fake_flower_workers,
    )

    snapshots, source, worker_count = await get_celery_queue_snapshots()
    assert source == "valkey"
    assert worker_count is None
    assert snapshots[0].depth == 1


@pytest.mark.asyncio
async def test_get_celery_queue_snapshots_prefers_flower(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_flower_depths() -> dict[str, int]:
        return {"critical": 3, "ingest": 0, "refresh": 0, "ai": 0, "notifications": 0, "maintenance": 0}

    async def fake_flower_workers() -> int:
        return 2

    async def fail_valkey() -> dict[str, int]:
        raise RuntimeError("should not reach valkey")

    monkeypatch.setattr(
        "app.services.platform.celery_queue_service._flower_queue_depths",
        fake_flower_depths,
    )
    monkeypatch.setattr(
        "app.services.platform.celery_queue_service._flower_worker_count",
        fake_flower_workers,
    )
    monkeypatch.setattr(
        "app.services.platform.celery_queue_service._valkey_queue_depths",
        fail_valkey,
    )

    snapshots, source, worker_count = await get_celery_queue_snapshots()
    assert source == "flower+workers"
    assert worker_count == 2
    assert snapshots[0].depth == 3
