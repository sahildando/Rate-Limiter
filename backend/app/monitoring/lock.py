"""Redis-backed distributed lock for monitor check execution."""

import uuid

import redis

from app.core.config import get_settings


def _lock_key(monitor_id: str | uuid.UUID) -> str:
    return f"monitor:lock:{monitor_id}"


def _pending_key(monitor_id: str | uuid.UUID) -> str:
    return f"monitor:pending:{monitor_id}"


class MonitorLock:
    """Distributed lock preventing concurrent checks for the same monitor."""

    def __init__(self, monitor_id: str | uuid.UUID, *, ttl_seconds: int | None = None) -> None:
        settings = get_settings()
        self._monitor_id = str(monitor_id)
        self._ttl_seconds = ttl_seconds or settings.monitor_lock_ttl_seconds
        self._redis: redis.Redis | None = None
        self._acquired = False

    def acquire(self) -> bool:
        """Attempt to acquire the lock. Returns True if successful."""
        if self._acquired:
            return True

        self._redis = redis.from_url(str(get_settings().redis_url), decode_responses=True)
        acquired = self._redis.set(
            _lock_key(self._monitor_id),
            "1",
            nx=True,
            ex=self._ttl_seconds,
        )
        if acquired:
            self._acquired = True
        return self._acquired

    def release(self) -> None:
        """Release the lock if held by this instance."""
        if self._redis is not None and self._acquired:
            self._redis.delete(_lock_key(self._monitor_id))
        self._acquired = False


def mark_monitor_pending(monitor_id: str | uuid.UUID, *, ttl_seconds: int | None = None) -> bool:
    """Mark a monitor as having a pending queued check. Returns False if already pending."""
    settings = get_settings()
    ttl = ttl_seconds or settings.monitor_pending_ttl_seconds
    client = redis.from_url(str(settings.redis_url), decode_responses=True)
    try:
        return bool(
            client.set(_pending_key(monitor_id), "1", nx=True, ex=ttl)
        )
    finally:
        client.close()


def clear_monitor_pending(monitor_id: str | uuid.UUID) -> None:
    """Clear the pending marker after a check completes or is skipped."""
    settings = get_settings()
    client = redis.from_url(str(settings.redis_url), decode_responses=True)
    try:
        client.delete(_pending_key(monitor_id))
    finally:
        client.close()
