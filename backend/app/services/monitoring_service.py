"""Monitoring execution and check persistence."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import ConflictError, NotFoundError
from app.core.idempotency import IdempotencyStore
from app.core.metrics import record_check_outcome
from app.models.check import Check
from app.models.monitor import Monitor, MonitorStatus
from app.models.user import User
from app.monitoring.checker import CheckOutcome, HttpChecker
from app.monitoring.lock import MonitorLock
from app.monitoring.retry import RetryConfig, calculate_backoff_seconds, is_retryable
from app.repositories.check_repository import CheckRepository
from app.repositories.monitor_repository import MonitorRepository
from app.schemas.check import CheckListResponse, CheckResponse

logger = structlog.get_logger(__name__)


class MonitoringService:
    """Runs HTTP checks and persists results. Callable by API or background workers."""

    def __init__(
        self,
        session: AsyncSession,
        checker: HttpChecker | None = None,
        *,
        retry_config: RetryConfig | None = None,
    ) -> None:
        self._session = session
        self._checker = checker or HttpChecker()
        self._checks = CheckRepository(session)
        self._monitors = MonitorRepository(session)
        self._retry_config = retry_config or _retry_config_from_settings(get_settings())

    async def run_check(self, monitor: Monitor, *, source: str = "api") -> Check:
        """Execute a check with retries, persist each attempt, and update monitor state."""
        config = self._retry_config
        final_check: Check | None = None

        for attempt in range(1, config.max_attempts + 1):
            outcome = await self._checker.check(monitor, attempt_number=attempt)
            final_check = await self._persist_check(monitor, outcome)
            record_check_outcome(outcome, source=source)

            if outcome.success:
                await self._apply_success(monitor, outcome)
                self._log_check_result(monitor, outcome)
                return final_check

            should_retry = attempt < config.max_attempts and is_retryable(outcome)
            if should_retry:
                delay = calculate_backoff_seconds(
                    attempt,
                    base_delay_seconds=config.base_delay_seconds,
                    max_delay_seconds=config.max_delay_seconds,
                )
                logger.info(
                    "monitor_check_retry_scheduled",
                    monitor_id=str(monitor.id),
                    attempt=attempt,
                    delay_seconds=round(delay, 3),
                    error_type=outcome.error_type.value if outcome.error_type else None,
                )
                await asyncio.sleep(delay)
                continue

            await self._apply_failure(monitor, outcome)
            self._log_check_result(monitor, outcome)
            return final_check

        if final_check is None:
            raise RuntimeError("run_check completed without producing a check record")
        return final_check

    async def run_check_by_monitor_id(self, monitor_id: uuid.UUID) -> Check | None:
        """Execute a check by monitor ID (used by background workers)."""
        monitor = await self._monitors.get_by_id(monitor_id)
        if monitor is None or not monitor.enabled:
            return None
        return await self.run_check(monitor, source="worker")

    async def trigger_check_for_user(
        self,
        user: User,
        monitor_id: uuid.UUID,
        *,
        idempotency_key: str | None = None,
        idempotency_store: IdempotencyStore | None = None,
    ) -> CheckResponse:
        """Run a manual check for a monitor owned by the user."""
        scope = f"manual-check:{user.id}:{monitor_id}"

        if idempotency_key and idempotency_store is not None:
            cached = await idempotency_store.begin(scope, idempotency_key)
            if cached is not None:
                return CheckResponse.model_validate(cached)

            try:
                response = await self._execute_manual_check(user, monitor_id)
            except Exception:
                await idempotency_store.abort(scope, idempotency_key)
                raise

            await idempotency_store.complete(
                scope,
                idempotency_key,
                response.model_dump(mode="json"),
            )
            return response

        return await self._execute_manual_check(user, monitor_id)

    async def _execute_manual_check(self, user: User, monitor_id: uuid.UUID) -> CheckResponse:
        """Execute a manual check with per-monitor locking."""
        monitor = await self._monitors.get_by_id_for_user(monitor_id, user.id)
        if monitor is None:
            raise NotFoundError("Monitor not found", code="MONITOR_NOT_FOUND")

        lock = MonitorLock(monitor_id)
        if not lock.acquire():
            raise ConflictError("Check already in progress", code="CHECK_IN_PROGRESS")

        try:
            check = await self.run_check(monitor)
        finally:
            lock.release()

        return CheckResponse.model_validate(check)

    async def list_checks_for_user(
        self,
        user: User,
        monitor_id: uuid.UUID,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> CheckListResponse:
        """Return paginated check history for a monitor owned by the user."""
        monitor = await self._monitors.get_by_id_for_user(monitor_id, user.id)
        if monitor is None:
            raise NotFoundError("Monitor not found", code="MONITOR_NOT_FOUND")

        checks, next_cursor = await self._checks.list_for_monitor(
            monitor_id,
            limit=limit,
            cursor=cursor,
        )
        return CheckListResponse(
            items=[CheckResponse.model_validate(c) for c in checks],
            next_cursor=next_cursor,
            limit=limit,
        )

    async def _persist_check(self, monitor: Monitor, outcome: CheckOutcome) -> Check:
        check = Check(
            monitor_id=monitor.id,
            status_code=outcome.status_code,
            response_time_ms=outcome.response_time_ms,
            success=outcome.success,
            error_type=outcome.error_type,
            error_message=outcome.error_message,
            attempt_number=outcome.attempt_number,
        )
        return await self._checks.create(check)

    async def _apply_success(self, monitor: Monitor, outcome: CheckOutcome) -> None:
        now = datetime.now(UTC)
        monitor.last_checked_at = now
        monitor.next_check_at = now + timedelta(seconds=monitor.interval_seconds)
        monitor.status = MonitorStatus.UP
        monitor.last_latency_ms = outcome.response_time_ms
        monitor.last_success_at = now
        monitor.consecutive_failure_count = 0
        await self._monitors.update(monitor)

    async def _apply_failure(self, monitor: Monitor, outcome: CheckOutcome) -> None:
        now = datetime.now(UTC)
        monitor.last_checked_at = now
        monitor.next_check_at = now + timedelta(seconds=monitor.interval_seconds)
        monitor.last_failure_at = now
        monitor.failure_count += 1
        monitor.consecutive_failure_count += 1

        threshold = self._retry_config.failure_threshold
        if monitor.consecutive_failure_count >= threshold:
            monitor.status = MonitorStatus.DOWN

        await self._monitors.update(monitor)

    def _log_check_result(self, monitor: Monitor, outcome: CheckOutcome) -> None:
        if outcome.success:
            logger.info(
                "monitor_check_completed",
                monitor_id=str(monitor.id),
                status=MonitorStatus.UP.value,
                status_code=outcome.status_code,
                latency_ms=outcome.response_time_ms,
                attempt=outcome.attempt_number,
            )
        else:
            logger.warning(
                "monitor_check_failed",
                monitor_id=str(monitor.id),
                error_type=outcome.error_type.value if outcome.error_type else None,
                attempt=outcome.attempt_number,
            )


def _retry_config_from_settings(settings: Settings) -> RetryConfig:
    return RetryConfig(
        max_attempts=settings.monitor_retry_max_attempts,
        base_delay_seconds=settings.monitor_retry_base_delay_seconds,
        max_delay_seconds=settings.monitor_retry_max_delay_seconds,
        failure_threshold=settings.monitor_failure_threshold,
    )
