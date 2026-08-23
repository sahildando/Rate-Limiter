"""Integration tests for retry behavior and failure state transitions."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.check import Check, CheckErrorType
from app.models.monitor import HttpMethod, Monitor, MonitorStatus
from app.monitoring.checker import CheckOutcome, HttpChecker
from app.monitoring.retry import RetryConfig
from app.repositories.monitor_repository import MonitorRepository
from app.repositories.user_repository import UserRepository
from app.services.monitoring_service import MonitoringService


async def _create_monitor(
    db_session: AsyncSession,
    *,
    status: MonitorStatus = MonitorStatus.UP,
    consecutive_failures: int = 0,
) -> Monitor:
    user = await UserRepository(db_session).create(
        email=f"reliability-{uuid.uuid4().hex[:8]}@example.com",
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
        status=status,
        failure_count=consecutive_failures,
        consecutive_failure_count=consecutive_failures,
    )
    return await MonitorRepository(db_session).create(monitor)


@pytest.mark.asyncio
async def test_single_failure_below_threshold_stays_up(db_session: AsyncSession) -> None:
    monitor = await _create_monitor(db_session, status=MonitorStatus.UP)
    checker = AsyncMock(spec=HttpChecker)
    checker.check.return_value = CheckOutcome(
        success=False,
        status_code=None,
        response_time_ms=100,
        error_type=CheckErrorType.TIMEOUT,
        error_message="Request timed out",
        attempt_number=1,
    )
    config = RetryConfig(max_attempts=1, failure_threshold=3)

    service = MonitoringService(db_session, checker, retry_config=config)
    await service.run_check(monitor)

    assert monitor.status == MonitorStatus.UP
    assert monitor.failure_count == 1
    assert monitor.consecutive_failure_count == 1


@pytest.mark.asyncio
async def test_failure_threshold_marks_monitor_down(db_session: AsyncSession) -> None:
    monitor = await _create_monitor(
        db_session,
        status=MonitorStatus.UP,
        consecutive_failures=2,
    )
    checker = AsyncMock(spec=HttpChecker)
    checker.check.return_value = CheckOutcome(
        success=False,
        status_code=503,
        response_time_ms=100,
        error_type=CheckErrorType.STATUS_CODE,
        error_message="Service unavailable",
        attempt_number=1,
    )
    config = RetryConfig(max_attempts=1, failure_threshold=3)

    service = MonitoringService(db_session, checker, retry_config=config)
    await service.run_check(monitor)

    assert monitor.status == MonitorStatus.DOWN
    assert monitor.consecutive_failure_count == 3


@pytest.mark.asyncio
async def test_success_recovers_down_monitor(db_session: AsyncSession) -> None:
    monitor = await _create_monitor(
        db_session,
        status=MonitorStatus.DOWN,
        consecutive_failures=5,
    )
    checker = AsyncMock(spec=HttpChecker)
    checker.check.return_value = CheckOutcome(
        success=True,
        status_code=200,
        response_time_ms=90,
        attempt_number=1,
    )
    config = RetryConfig(max_attempts=1, failure_threshold=3)

    service = MonitoringService(db_session, checker, retry_config=config)
    await service.run_check(monitor)

    assert monitor.status == MonitorStatus.UP
    assert monitor.consecutive_failure_count == 0


@pytest.mark.asyncio
async def test_retry_succeeds_on_second_attempt(db_session: AsyncSession) -> None:
    monitor = await _create_monitor(db_session, status=MonitorStatus.UP)
    checker = AsyncMock(spec=HttpChecker)
    checker.check.side_effect = [
        CheckOutcome(
            success=False,
            status_code=None,
            response_time_ms=100,
            error_type=CheckErrorType.TIMEOUT,
            error_message="Request timed out",
            attempt_number=1,
        ),
        CheckOutcome(
            success=True,
            status_code=200,
            response_time_ms=80,
            attempt_number=2,
        ),
    ]
    config = RetryConfig(max_attempts=3, base_delay_seconds=0.01, failure_threshold=3)

    service = MonitoringService(db_session, checker, retry_config=config)
    with patch("app.services.monitoring_service.asyncio.sleep", new=AsyncMock()):
        check = await service.run_check(monitor)

    assert check.success is True
    assert check.attempt_number == 2
    assert monitor.status == MonitorStatus.UP
    assert monitor.consecutive_failure_count == 0
    assert checker.check.await_count == 2

    result = await db_session.execute(select(Check).where(Check.monitor_id == monitor.id))
    checks = list(result.scalars().all())
    assert len(checks) == 2


@pytest.mark.asyncio
async def test_non_retryable_failure_does_not_retry(db_session: AsyncSession) -> None:
    monitor = await _create_monitor(db_session, status=MonitorStatus.UP)
    checker = AsyncMock(spec=HttpChecker)
    checker.check.return_value = CheckOutcome(
        success=False,
        status_code=404,
        response_time_ms=50,
        error_type=CheckErrorType.STATUS_CODE,
        error_message="Not found",
        attempt_number=1,
    )
    config = RetryConfig(max_attempts=3, failure_threshold=3)

    service = MonitoringService(db_session, checker, retry_config=config)
    with patch("app.services.monitoring_service.asyncio.sleep", new=AsyncMock()) as sleep_mock:
        await service.run_check(monitor)

    checker.check.assert_awaited_once()
    sleep_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_transient_failure_retries_until_exhausted(db_session: AsyncSession) -> None:
    monitor = await _create_monitor(db_session, status=MonitorStatus.UP)
    checker = AsyncMock(spec=HttpChecker)
    checker.check.return_value = CheckOutcome(
        success=False,
        status_code=None,
        response_time_ms=100,
        error_type=CheckErrorType.CONNECTION,
        error_message="Connection failed",
        attempt_number=1,
    )
    config = RetryConfig(max_attempts=3, base_delay_seconds=0.01, failure_threshold=3)

    service = MonitoringService(db_session, checker, retry_config=config)
    with patch("app.services.monitoring_service.asyncio.sleep", new=AsyncMock()):
        check = await service.run_check(monitor)

    assert check.success is False
    assert checker.check.await_count == 3

    result = await db_session.execute(select(Check).where(Check.monitor_id == monitor.id))
    assert len(list(result.scalars().all())) == 3
