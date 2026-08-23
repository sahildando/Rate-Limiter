"""Unit tests for distributed monitor locks."""

import uuid

import pytest
import redis

from app.monitoring.lock import (
    MonitorLock,
    clear_monitor_pending,
    mark_monitor_pending,
)


@pytest.fixture
def redis_client():
    import os

    client = redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    client.flushdb()
    yield client
    client.flushdb()
    client.close()


def test_monitor_lock_acquire_and_release(redis_client) -> None:
    monitor_id = str(uuid.uuid4())
    lock = MonitorLock(monitor_id)

    assert lock.acquire() is True

    other = MonitorLock(monitor_id)
    assert other.acquire() is False

    lock.release()

    third = MonitorLock(monitor_id)
    assert third.acquire() is True
    third.release()


def test_monitor_lock_blocks_concurrent_workers(redis_client) -> None:
    monitor_id = str(uuid.uuid4())
    worker_a = MonitorLock(monitor_id)
    worker_b = MonitorLock(monitor_id)

    assert worker_a.acquire() is True
    assert worker_b.acquire() is False

    worker_a.release()
    assert worker_b.acquire() is True
    worker_b.release()


def test_mark_monitor_pending_deduplication(redis_client) -> None:
    monitor_id = str(uuid.uuid4())

    assert mark_monitor_pending(monitor_id) is True
    assert mark_monitor_pending(monitor_id) is False

    clear_monitor_pending(monitor_id)
    assert mark_monitor_pending(monitor_id) is True
