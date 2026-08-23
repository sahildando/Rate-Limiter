"""Check persistence layer."""

import base64
import uuid
from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.check import Check
from app.models.monitor import Monitor
from app.repositories.stats_types import MonitorStatsAggregation, UserChecksAggregation


class CheckRepository:
    """Data access for monitor check records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, check: Check) -> Check:
        self._session.add(check)
        await self._session.flush()
        await self._session.refresh(check)
        return check

    async def list_for_monitor(
        self,
        monitor_id: uuid.UUID,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[Check], str | None]:
        query = select(Check).where(Check.monitor_id == monitor_id)

        if cursor is not None:
            cursor_checked_at, cursor_id = decode_check_cursor(cursor)
            query = query.where(
                or_(
                    Check.checked_at < cursor_checked_at,
                    and_(Check.checked_at == cursor_checked_at, Check.id < cursor_id),
                )
            )

        query = query.order_by(Check.checked_at.desc(), Check.id.desc()).limit(limit + 1)
        result = await self._session.execute(query)
        checks = list(result.scalars().all())

        next_cursor = None
        if len(checks) > limit:
            last = checks[limit - 1]
            next_cursor = encode_check_cursor(last.checked_at, last.id)
            checks = checks[:limit]

        return checks, next_cursor

    async def aggregate_stats_for_monitor(
        self,
        monitor_id: uuid.UUID,
        since: datetime,
    ) -> MonitorStatsAggregation:
        """Aggregate uptime and latency statistics for a monitor within a time window."""
        latency_filter = and_(
            Check.success.is_(True),
            Check.response_time_ms.is_not(None),
        )

        result = await self._session.execute(
            select(
                func.count().label("total_checks"),
                func.count().filter(Check.success.is_(True)).label("successful_checks"),
                func.avg(Check.response_time_ms).filter(latency_filter).label("avg_latency_ms"),
                func.min(Check.response_time_ms).filter(latency_filter).label("min_latency_ms"),
                func.max(Check.response_time_ms).filter(latency_filter).label("max_latency_ms"),
                func.percentile_cont(0.95)
                .within_group(Check.response_time_ms)
                .filter(latency_filter)
                .label("p95_latency_ms"),
            ).where(
                Check.monitor_id == monitor_id,
                Check.checked_at >= since,
            )
        )
        row = result.one()

        latest_result = await self._session.execute(
            select(Check.response_time_ms)
            .where(
                Check.monitor_id == monitor_id,
                Check.checked_at >= since,
                latency_filter,
            )
            .order_by(Check.checked_at.desc())
            .limit(1)
        )
        latest_latency_ms = latest_result.scalar_one_or_none()

        return MonitorStatsAggregation(
            total_checks=int(row.total_checks or 0),
            successful_checks=int(row.successful_checks or 0),
            avg_latency_ms=float(row.avg_latency_ms) if row.avg_latency_ms is not None else None,
            min_latency_ms=int(row.min_latency_ms) if row.min_latency_ms is not None else None,
            max_latency_ms=int(row.max_latency_ms) if row.max_latency_ms is not None else None,
            p95_latency_ms=float(row.p95_latency_ms) if row.p95_latency_ms is not None else None,
            latest_latency_ms=latest_latency_ms,
        )

    async def aggregate_stats_for_user(
        self,
        user_id: uuid.UUID,
        since: datetime,
    ) -> UserChecksAggregation:
        """Aggregate check statistics across all monitors owned by a user."""
        latency_filter = and_(
            Check.success.is_(True),
            Check.response_time_ms.is_not(None),
        )

        result = await self._session.execute(
            select(
                func.count().label("total_checks"),
                func.count().filter(Check.success.is_(True)).label("successful_checks"),
                func.avg(Check.response_time_ms).filter(latency_filter).label("average_latency_ms"),
            )
            .select_from(Check)
            .join(Monitor, Monitor.id == Check.monitor_id)
            .where(
                Monitor.user_id == user_id,
                Check.checked_at >= since,
            )
        )
        row = result.one()

        return UserChecksAggregation(
            total_checks=int(row.total_checks or 0),
            successful_checks=int(row.successful_checks or 0),
            average_latency_ms=(
                float(row.average_latency_ms) if row.average_latency_ms is not None else None
            ),
        )


def encode_check_cursor(checked_at: datetime, check_id: uuid.UUID) -> str:
    """Encode a composite cursor from check timestamp and ID."""
    raw = f"{checked_at.isoformat()}|{check_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_check_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    """Decode a composite check cursor."""
    raw = base64.urlsafe_b64decode(cursor.encode()).decode()
    checked_at_str, check_id_str = raw.split("|", 1)
    return datetime.fromisoformat(checked_at_str), uuid.UUID(check_id_str)
