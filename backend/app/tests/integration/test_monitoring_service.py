"""Integration tests for monitoring service and check persistence."""

import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.check import CheckErrorType
from app.models.monitor import HttpMethod, Monitor, MonitorStatus
from app.monitoring.checker import CheckOutcome, HttpChecker
from app.repositories.monitor_repository import MonitorRepository
from app.repositories.user_repository import UserRepository
from app.services.monitoring_service import MonitoringService


async def _create_monitor(db_session: AsyncSession) -> Monitor:
    user = await UserRepository(db_session).create(
        email=f"monitor-user-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("securepassword123"),
    )
    monitor = Monitor(
        user_id=user.id,
        name="API",
        url="https://example.com/health",
        method=HttpMethod.GET,
        expected_status_code=200,
        interval_seconds=60,
        timeout_ms=5000,
        enabled=True,
        status=MonitorStatus.PENDING,
        failure_count=0,
        consecutive_failure_count=0,
    )
    return await MonitorRepository(db_session).create(monitor)


@pytest.mark.asyncio
async def test_run_check_persists_success(db_session: AsyncSession) -> None:
    monitor = await _create_monitor(db_session)
    checker = AsyncMock(spec=HttpChecker)
    checker.check.return_value = CheckOutcome(
        success=True,
        status_code=200,
        response_time_ms=142,
    )

    service = MonitoringService(db_session, checker)
    check = await service.run_check(monitor)

    assert check.success is True
    assert check.status_code == 200
    assert check.response_time_ms == 142
    assert monitor.status == MonitorStatus.UP
    assert monitor.last_latency_ms == 142
    assert monitor.consecutive_failure_count == 0
    assert monitor.last_checked_at is not None


@pytest.mark.asyncio
async def test_run_check_persists_failure(db_session: AsyncSession) -> None:
    monitor = await _create_monitor(db_session)
    checker = AsyncMock(spec=HttpChecker)
    checker.check.return_value = CheckOutcome(
        success=False,
        status_code=None,
        response_time_ms=5000,
        error_type=CheckErrorType.TIMEOUT,
        error_message="Request timed out",
    )

    service = MonitoringService(db_session, checker)
    check = await service.run_check(monitor)

    assert check.success is False
    assert check.error_type == CheckErrorType.TIMEOUT
    assert monitor.status == MonitorStatus.PENDING
    assert monitor.failure_count == 1
    assert monitor.consecutive_failure_count == 1


@pytest.mark.asyncio
async def test_run_check_schedules_next_check(db_session: AsyncSession) -> None:
    monitor = await _create_monitor(db_session)
    checker = AsyncMock(spec=HttpChecker)
    checker.check.return_value = CheckOutcome(success=True, status_code=200, response_time_ms=50)

    service = MonitoringService(db_session, checker)
    await service.run_check(monitor)

    assert monitor.next_check_at is not None
    assert monitor.last_checked_at is not None
