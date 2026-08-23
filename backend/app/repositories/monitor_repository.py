"""Monitor persistence layer."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.monitor import Monitor, MonitorStatus


class MonitorRepository:
    """Data access for monitors with ownership enforcement."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, monitor_id: uuid.UUID) -> Monitor | None:
        """Return a monitor by ID (used by background workers)."""
        result = await self._session.execute(select(Monitor).where(Monitor.id == monitor_id))
        return result.scalar_one_or_none()

    async def get_by_id_for_user(self, monitor_id: uuid.UUID, user_id: uuid.UUID) -> Monitor | None:
        """Return a monitor only if it belongs to the given user."""
        result = await self._session.execute(
            select(Monitor).where(Monitor.id == monitor_id, Monitor.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Monitor], int]:
        count_result = await self._session.execute(
            select(func.count()).select_from(Monitor).where(Monitor.user_id == user_id)
        )
        total = count_result.scalar_one() or 0

        result = await self._session.execute(
            select(Monitor)
            .where(Monitor.user_id == user_id)
            .order_by(Monitor.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def count_status_for_user(self, user_id: uuid.UUID) -> tuple[int, int, int]:
        """Return total, up, and down monitor counts for a user."""
        total_result = await self._session.execute(
            select(func.count()).select_from(Monitor).where(Monitor.user_id == user_id)
        )
        up_result = await self._session.execute(
            select(func.count())
            .select_from(Monitor)
            .where(Monitor.user_id == user_id, Monitor.status == MonitorStatus.UP)
        )
        down_result = await self._session.execute(
            select(func.count())
            .select_from(Monitor)
            .where(Monitor.user_id == user_id, Monitor.status == MonitorStatus.DOWN)
        )

        return (
            int(total_result.scalar_one() or 0),
            int(up_result.scalar_one() or 0),
            int(down_result.scalar_one() or 0),
        )

    async def create(self, monitor: Monitor) -> Monitor:
        self._session.add(monitor)
        await self._session.flush()
        await self._session.refresh(monitor)
        return monitor

    async def update(self, monitor: Monitor) -> Monitor:
        await self._session.flush()
        await self._session.refresh(monitor)
        return monitor

    async def delete(self, monitor: Monitor) -> None:
        await self._session.delete(monitor)
        await self._session.flush()

    async def list_due_enabled(self, *, limit: int = 100) -> list[Monitor]:
        """Return enabled monitors that are due for their next check."""
        now = datetime.now(UTC)
        result = await self._session.execute(
            select(Monitor)
            .where(
                Monitor.enabled.is_(True),
                or_(Monitor.next_check_at.is_(None), Monitor.next_check_at <= now),
            )
            .order_by(Monitor.next_check_at.asc().nullsfirst())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def schedule_next_check(self, monitor: Monitor) -> Monitor:
        """Advance next_check_at to prevent duplicate scheduler enqueue."""
        now = datetime.now(UTC)
        monitor.next_check_at = now + timedelta(seconds=monitor.interval_seconds)
        await self._session.flush()
        await self._session.refresh(monitor)
        return monitor
