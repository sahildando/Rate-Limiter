"""Redis-backed idempotency for manual check requests."""

import json
from typing import Any

import redis.asyncio as aioredis

from app.core.config import Settings, get_settings
from app.core.exceptions import ConflictError

_PROCESSING = "__processing__"


class IdempotencyStore:
    """
    Store idempotency results in Redis.

    Tradeoff vs PostgreSQL: Redis offers low-latency NX/set with TTL suitable for
    short-lived duplicate suppression across API instances. PostgreSQL would add
    durability and auditability but higher write latency and requires cleanup jobs.
    """

    def __init__(self, redis_client: aioredis.Redis, settings: Settings | None = None) -> None:
        self._redis = redis_client
        self._settings = settings or get_settings()

    def _key(self, scope: str, idempotency_key: str) -> str:
        return f"idempotency:{scope}:{idempotency_key}"

    async def begin(self, scope: str, idempotency_key: str) -> dict[str, Any] | None:
        """
        Begin an idempotent operation.

        Returns cached response if already completed, or None if this caller should execute.
        Raises ConflictError if another request with the same key is in progress.
        """
        key = self._key(scope, idempotency_key)
        existing = await self._redis.get(key)
        if existing is not None:
            if existing == _PROCESSING:
                raise ConflictError(
                    "Duplicate idempotent request is already in progress",
                    code="IDEMPOTENCY_IN_PROGRESS",
                )
            return json.loads(existing)

        acquired = await self._redis.set(
            key,
            _PROCESSING,
            nx=True,
            ex=self._settings.idempotency_ttl_seconds,
        )
        if not acquired:
            existing = await self._redis.get(key)
            if existing == _PROCESSING:
                raise ConflictError(
                    "Duplicate idempotent request is already in progress",
                    code="IDEMPOTENCY_IN_PROGRESS",
                )
            if existing is not None:
                return json.loads(existing)

        return None

    async def complete(self, scope: str, idempotency_key: str, payload: dict[str, Any]) -> None:
        """Persist the completed response for future duplicate requests."""
        key = self._key(scope, idempotency_key)
        await self._redis.set(
            key,
            json.dumps(payload),
            ex=self._settings.idempotency_ttl_seconds,
        )

    async def abort(self, scope: str, idempotency_key: str) -> None:
        """Remove in-progress marker when execution fails."""
        key = self._key(scope, idempotency_key)
        current = await self._redis.get(key)
        if current == _PROCESSING:
            await self._redis.delete(key)
