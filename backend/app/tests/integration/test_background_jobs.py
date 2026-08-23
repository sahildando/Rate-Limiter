"""Integration tests for Celery tasks and scheduler."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.session import dispose_engine
from app.models.monitor import HttpMethod, Monitor, MonitorStatus
from app.monitoring.lock import MonitorLock
from app.monitoring.scheduler import poll_and_enqueue
from app.monitoring.tasks import run_monitor_check
from app.repositories.monitor_repository import MonitorRepository
from app.repositories.user_repository import UserRepository


@pytest.fixture
def celery_eager():
    from app.monitoring.celery_app import celery_app

    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield celery_app
    celery_app.conf.task_always_eager = False
    celery_app.conf.task_eager_propagates = False


@pytest.fixture
def redis_client():
    import os

    import redis

    client = redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    client.flushdb()
    yield client
    client.flushdb()
    client.close()


async def _create_due_monitor(db_session: AsyncSession) -> Monitor:
    user = await UserRepository(db_session).create(
        email=f"worker-user-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("securepassword123"),
    )
    monitor = Monitor(
        user_id=user.id,
        name="Worker Test",
        url="https://example.com/health",
        method=HttpMethod.GET,
        expected_status_code=200,
        interval_seconds=60,
        timeout_ms=5000,
        enabled=True,
        status=MonitorStatus.PENDING,
        failure_count=0,
        consecutive_failure_count=0,
        next_check_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    return await MonitorRepository(db_session).create(monitor)


@pytest.mark.asyncio
async def test_list_due_enabled_returns_past_monitors(db_session: AsyncSession) -> None:
    monitor = await _create_due_monitor(db_session)
    repo = MonitorRepository(db_session)

    due = await repo.list_due_enabled()
    assert any(m.id == monitor.id for m in due)


@pytest.mark.asyncio
@patch("app.monitoring.scheduler.run_monitor_check.delay")
async def test_poll_and_enqueue_schedules_due_monitors(
    mock_delay: MagicMock,
    db_session: AsyncSession,
    redis_client,
) -> None:
    await _create_due_monitor(db_session)
    await db_session.commit()
    await dispose_engine()

    count = await poll_and_enqueue()
    assert count == 1
    mock_delay.assert_called_once()


@pytest.mark.asyncio
@patch("app.monitoring.scheduler.run_monitor_check.delay")
async def test_poll_skips_already_pending_monitors(
    mock_delay: MagicMock,
    db_session: AsyncSession,
    redis_client,
) -> None:
    monitor = await _create_due_monitor(db_session)
    await db_session.commit()
    await dispose_engine()

    first = await poll_and_enqueue()
    second = await poll_and_enqueue()

    assert first == 1
    assert second == 0
    mock_delay.assert_called_once_with(str(monitor.id))


def test_celery_task_skips_when_lock_held(
    celery_eager,
    redis_client,
) -> None:
    monitor_id = str(uuid.uuid4())
    lock = MonitorLock(monitor_id)
    assert lock.acquire()

    try:
        result = run_monitor_check.apply(args=[monitor_id]).get()
        assert result["status"] == "skipped"
        assert result["reason"] == "lock_not_acquired"
    finally:
        lock.release()


def test_celery_task_executes_check(celery_eager, redis_client) -> None:
    monitor_id = str(uuid.uuid4())
    expected = {
        "status": "completed",
        "check_id": str(uuid.uuid4()),
        "success": True,
    }

    with patch("app.monitoring.tasks._run_async", return_value=expected):
        result = run_monitor_check.apply(args=[monitor_id]).get()

    assert result == expected
