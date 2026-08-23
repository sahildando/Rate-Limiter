"""Analytics business logic."""

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.user import User
from app.repositories.check_repository import CheckRepository
from app.repositories.monitor_repository import MonitorRepository
from app.repositories.stats_types import MonitorStatsAggregation
from app.schemas.stats import (
    DashboardSummaryResponse,
    LatencyStats,
    MonitorStatsResponse,
    StatsPeriod,
    calculate_uptime_percentage,
    period_window,
)


class AnalyticsService:
    """Derives uptime and latency statistics from historical check records."""

    def __init__(self, session: AsyncSession) -> None:
        self._monitors = MonitorRepository(session)
        self._checks = CheckRepository(session)

    async def get_monitor_stats(
        self,
        user: User,
        monitor_id: uuid.UUID,
        period: StatsPeriod,
    ) -> MonitorStatsResponse:
        """Return aggregated statistics for a monitor owned by the user."""
        monitor = await self._monitors.get_by_id_for_user(monitor_id, user.id)
        if monitor is None:
            raise NotFoundError("Monitor not found", code="MONITOR_NOT_FOUND")

        window_start, window_end = period_window(period)
        aggregation = await self._checks.aggregate_stats_for_monitor(monitor_id, window_start)
        return _build_monitor_stats_response(
            monitor_id=monitor_id,
            period=period,
            window_start=window_start,
            window_end=window_end,
            aggregation=aggregation,
        )

    async def get_dashboard_summary(
        self,
        user: User,
        period: StatsPeriod,
    ) -> DashboardSummaryResponse:
        """Return cross-monitor summary statistics for the user's dashboard."""
        window_start, window_end = period_window(period)
        total_monitors, up_monitors, down_monitors = await self._monitors.count_status_for_user(
            user.id
        )
        check_stats = await self._checks.aggregate_stats_for_user(user.id, window_start)

        return DashboardSummaryResponse(
            period=period,
            from_=window_start,
            to=window_end,
            total_monitors=total_monitors,
            up_monitors=up_monitors,
            down_monitors=down_monitors,
            overall_uptime_percentage=calculate_uptime_percentage(
                check_stats.total_checks,
                check_stats.successful_checks,
            ),
            average_latency_ms=(
                round(check_stats.average_latency_ms, 2)
                if check_stats.average_latency_ms is not None
                else None
            ),
        )


def _build_monitor_stats_response(
    *,
    monitor_id: uuid.UUID,
    period: StatsPeriod,
    window_start: datetime,
    window_end: datetime,
    aggregation: MonitorStatsAggregation,
) -> MonitorStatsResponse:
    return MonitorStatsResponse(
        monitor_id=monitor_id,
        period=period,
        from_=window_start,
        to=window_end,
        total_checks=aggregation.total_checks,
        successful_checks=aggregation.successful_checks,
        uptime_percentage=calculate_uptime_percentage(
            aggregation.total_checks,
            aggregation.successful_checks,
        ),
        latency_ms=LatencyStats(
            latest=aggregation.latest_latency_ms,
            avg=(
                round(aggregation.avg_latency_ms, 2)
                if aggregation.avg_latency_ms is not None
                else None
            ),
            min=aggregation.min_latency_ms,
            max=aggregation.max_latency_ms,
            p95=(
                round(aggregation.p95_latency_ms, 2)
                if aggregation.p95_latency_ms is not None
                else None
            ),
        ),
    )
