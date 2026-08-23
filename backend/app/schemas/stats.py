"""Analytics and statistics API schemas."""

import enum
import uuid
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field


class StatsPeriod(enum.StrEnum):
    """Supported time windows for aggregated statistics."""

    HOUR_1 = "1h"
    HOURS_24 = "24h"
    DAYS_7 = "7d"
    DAYS_30 = "30d"


_PERIOD_DELTAS: dict[StatsPeriod, timedelta] = {
    StatsPeriod.HOUR_1: timedelta(hours=1),
    StatsPeriod.HOURS_24: timedelta(hours=24),
    StatsPeriod.DAYS_7: timedelta(days=7),
    StatsPeriod.DAYS_30: timedelta(days=30),
}


def period_to_timedelta(period: StatsPeriod) -> timedelta:
    """Return the timedelta for a stats period."""
    return _PERIOD_DELTAS[period]


def period_window(period: StatsPeriod, *, now: datetime | None = None) -> tuple[datetime, datetime]:
    """Return inclusive-exclusive window bounds (from, to) for a stats period."""
    end = now or datetime.now(UTC)
    start = end - period_to_timedelta(period)
    return start, end


def calculate_uptime_percentage(total_checks: int, successful_checks: int) -> float | None:
    """Compute uptime percentage; returns None when there are no checks in the window."""
    if total_checks == 0:
        return None
    return round((successful_checks / total_checks) * 100, 2)


class LatencyStats(BaseModel):
    """Latency statistics derived from successful checks."""

    latest: int | None = None
    avg: float | None = None
    min: int | None = None
    max: int | None = None
    p95: float | None = None


class MonitorStatsResponse(BaseModel):
    """Aggregated uptime and latency statistics for a single monitor."""

    monitor_id: uuid.UUID
    period: StatsPeriod
    from_: datetime = Field(serialization_alias="from")
    to: datetime
    total_checks: int
    successful_checks: int
    uptime_percentage: float | None
    latency_ms: LatencyStats


class DashboardSummaryResponse(BaseModel):
    """Cross-monitor summary for the authenticated user's dashboard."""

    period: StatsPeriod
    from_: datetime = Field(serialization_alias="from")
    to: datetime
    total_monitors: int
    up_monitors: int
    down_monitors: int
    overall_uptime_percentage: float | None
    average_latency_ms: float | None
