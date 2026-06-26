"""Unit tests for queue depth trend stubs."""

from app.services.platform.celery_queue_service import depth_trend_stub


def test_depth_trend_stub_zero() -> None:
    assert depth_trend_stub(0) == [0, 0, 0]


def test_depth_trend_stub_positive() -> None:
    trend = depth_trend_stub(100)
    assert len(trend) == 3
    assert trend[-1] == 100
    assert trend[0] <= trend[1] <= trend[2]
