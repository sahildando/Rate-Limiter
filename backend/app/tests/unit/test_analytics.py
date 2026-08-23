"""Unit tests for analytics helpers."""

from datetime import UTC, datetime, timedelta

import pytest

from app.schemas.stats import (
    StatsPeriod,
    calculate_uptime_percentage,
    period_to_timedelta,
    period_window,
)


def test_period_to_timedelta() -> None:
    assert period_to_timedelta(StatsPeriod.HOUR_1) == timedelta(hours=1)
    assert period_to_timedelta(StatsPeriod.HOURS_24) == timedelta(hours=24)
    assert period_to_timedelta(StatsPeriod.DAYS_7) == timedelta(days=7)
    assert period_to_timedelta(StatsPeriod.DAYS_30) == timedelta(days=30)


def test_period_window() -> None:
    now = datetime(2026, 8, 23, 12, 0, tzinfo=UTC)
    start, end = period_window(StatsPeriod.HOURS_24, now=now)
    assert end == now
    assert start == now - timedelta(hours=24)


@pytest.mark.parametrize(
    ("total", "successful", "expected"),
    [
        (0, 0, None),
        (10, 10, 100.0),
        (4, 3, 75.0),
        (3, 2, 66.67),
    ],
)
def test_calculate_uptime_percentage(total: int, successful: int, expected: float | None) -> None:
    assert calculate_uptime_percentage(total, successful) == expected
