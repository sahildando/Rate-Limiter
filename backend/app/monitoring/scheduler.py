"""Scheduler that enqueues due monitor checks."""

import asyncio

import structlog

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import dispose_engine, get_session_factory
from app.monitoring.lock import mark_monitor_pending
from app.monitoring.tasks import run_monitor_check
from app.repositories.monitor_repository import MonitorRepository

logger = structlog.get_logger(__name__)


async def poll_and_enqueue() -> int:
    """Find enabled monitors due for checking and enqueue Celery tasks."""
    settings = get_settings()
    session_factory = get_session_factory(settings)
    enqueued = 0

    async with session_factory() as session:
        repo = MonitorRepository(session)
        due_monitors = await repo.list_due_enabled(limit=settings.scheduler_batch_size)

        for monitor in due_monitors:
            monitor_id = str(monitor.id)
            if not mark_monitor_pending(monitor_id):
                logger.debug(
                    "monitor_enqueue_skipped",
                    monitor_id=monitor_id,
                    reason="already_pending",
                )
                continue

            await repo.schedule_next_check(monitor)
            run_monitor_check.delay(monitor_id)
            enqueued += 1
            logger.info("monitor_check_enqueued", monitor_id=monitor_id)

        await session.commit()

    return enqueued


async def run_scheduler() -> None:
    """Run the scheduler loop until interrupted."""
    settings = get_settings()
    logger.info(
        "scheduler_started",
        poll_interval_seconds=settings.scheduler_poll_interval_seconds,
        batch_size=settings.scheduler_batch_size,
    )

    while True:
        try:
            count = await poll_and_enqueue()
            logger.debug("scheduler_poll_completed", enqueued=count)
        except Exception:
            logger.exception("scheduler_poll_failed")

        await asyncio.sleep(settings.scheduler_poll_interval_seconds)


def main() -> None:
    """Entry point for the scheduler process."""
    configure_logging()
    try:
        asyncio.run(run_scheduler())
    except KeyboardInterrupt:
        logger.info("scheduler_stopped")
    finally:
        asyncio.run(dispose_engine())


if __name__ == "__main__":
    main()
