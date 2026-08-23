"""Monitor business logic."""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.monitor import Monitor, MonitorStatus
from app.models.user import User
from app.monitoring.ssrf import validate_monitor_url
from app.repositories.monitor_repository import MonitorRepository
from app.schemas.monitor import (
    MonitorCreateRequest,
    MonitorListResponse,
    MonitorResponse,
    MonitorUpdateRequest,
)


class MonitorService:
    """Handles monitor CRUD with ownership enforcement."""

    def __init__(self, session: AsyncSession) -> None:
        self._monitors = MonitorRepository(session)

    async def create_monitor(self, user: User, data: MonitorCreateRequest) -> MonitorResponse:
        await validate_monitor_url(str(data.url))
        now = datetime.now(UTC)
        monitor = Monitor(
            user_id=user.id,
            name=data.name,
            url=str(data.url),
            method=data.method,
            expected_status_code=data.expected_status_code,
            interval_seconds=data.interval,
            timeout_ms=data.timeout,
            enabled=data.enabled,
            status=MonitorStatus.PENDING,
            next_check_at=now,
        )
        created = await self._monitors.create(monitor)
        return MonitorResponse.model_validate(created)

    async def get_monitor(self, user: User, monitor_id: uuid.UUID) -> MonitorResponse:
        monitor = await self._get_owned_monitor(user.id, monitor_id)
        return MonitorResponse.model_validate(monitor)

    async def list_monitors(
        self,
        user: User,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> MonitorListResponse:
        monitors, total = await self._monitors.list_for_user(user.id, offset=offset, limit=limit)
        return MonitorListResponse(
            items=[MonitorResponse.model_validate(m) for m in monitors],
            total=total,
            offset=offset,
            limit=limit,
        )

    async def update_monitor(
        self,
        user: User,
        monitor_id: uuid.UUID,
        data: MonitorUpdateRequest,
    ) -> MonitorResponse:
        monitor = await self._get_owned_monitor(user.id, monitor_id)

        update_data = data.model_dump(exclude_unset=True)
        field_map = {"interval": "interval_seconds", "timeout": "timeout_ms"}
        for key, value in update_data.items():
            attr = field_map.get(key, key)
            if attr == "url" and value is not None:
                value = str(value)
                await validate_monitor_url(value)
            setattr(monitor, attr, value)

        updated = await self._monitors.update(monitor)
        return MonitorResponse.model_validate(updated)

    async def delete_monitor(self, user: User, monitor_id: uuid.UUID) -> None:
        monitor = await self._get_owned_monitor(user.id, monitor_id)
        await self._monitors.delete(monitor)

    async def _get_owned_monitor(self, user_id: uuid.UUID, monitor_id: uuid.UUID) -> Monitor:
        monitor = await self._monitors.get_by_id_for_user(monitor_id, user_id)
        if monitor is None:
            raise NotFoundError("Monitor not found", code="MONITOR_NOT_FOUND")
        return monitor
