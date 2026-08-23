"""Celery tasks for background monitor checks."""

import asyncio
import uuid
from collections.abc import Coroutine
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import structlog

from app.core.config import get_settings
from app.core.metrics import record_worker_failure, record_worker_skipped
from app.db.session import get_session_factory
from app.monitoring.celery_app import celery_app
from app.monitoring.lock import MonitorLock, clear_monitor_pending
from app.services.monitoring_service import MonitoringService

logger = structlog.get_logger(__name__)

_executor = ThreadPoolExecutor(max_workers=1)


def _run_async[T](coro: Coroutine[Any, Any, T]) -> T:
    """Run async code from Celery's synchronous worker context."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    future = _executor.submit(asyncio.run, coro)
    return future.result()


@celery_app.task(name="monitoring.run_monitor_check", bind=True, max_retries=0)
def run_monitor_check(self, monitor_id: str) -> dict[str, object]:
    """Execute a monitor check in a Celery worker with distributed locking."""
    lock = MonitorLock(monitor_id)
    if not lock.acquire():
        logger.info(
            "monitor_check_skipped",
            monitor_id=monitor_id,
            reason="lock_not_acquired",
        )
        record_worker_skipped(reason="lock_not_acquired")
        clear_monitor_pending(monitor_id)
        return {"status": "skipped", "reason": "lock_not_acquired"}

    try:
        result = _run_async(_execute_check(monitor_id))
        logger.info("monitor_check_task_completed", monitor_id=monitor_id, **result)
        return result
    except Exception:
        record_worker_failure()
        logger.exception("monitor_check_task_failed", monitor_id=monitor_id)
        raise
    finally:
        lock.release()
        clear_monitor_pending(monitor_id)


async def _execute_check(monitor_id: str) -> dict[str, object]:
    """Run the async monitoring service inside the worker."""
    session_factory = get_session_factory(get_settings())
    async with session_factory() as session:
        service = MonitoringService(session)
        check = await service.run_check_by_monitor_id(uuid.UUID(monitor_id))
        if check is None:
            await session.commit()
            record_worker_skipped(reason="monitor_not_found_or_disabled")
            return {"status": "skipped", "reason": "monitor_not_found_or_disabled"}

        await session.commit()
        return {
            "status": "completed",
            "check_id": str(check.id),
            "success": check.success,
        }
