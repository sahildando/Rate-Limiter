"""Unit tests for idempotency store."""

import pytest
import redis.asyncio as aioredis

from app.core.config import Settings
from app.core.exceptions import ConflictError
from app.core.idempotency import IdempotencyStore


@pytest.fixture
def idempotency_settings() -> Settings:
    return Settings(
        environment="test",
        database_url="postgresql+asyncpg://monitoring:monitoring@localhost:5433/monitoring_test",
        redis_url="redis://localhost:6380/1",
        idempotency_ttl_seconds=3600,
    )


@pytest.mark.asyncio
async def test_begin_complete_returns_cached_result(idempotency_settings: Settings) -> None:
    client = aioredis.from_url(str(idempotency_settings.redis_url), decode_responses=True)
    try:
        await client.flushdb()
        store = IdempotencyStore(client, idempotency_settings)

        assert await store.begin("scope", "key-1") is None
        await store.complete("scope", "key-1", {"success": True, "id": "abc"})

        cached = await store.begin("scope", "key-1")
        assert cached == {"success": True, "id": "abc"}
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_begin_raises_when_in_progress(idempotency_settings: Settings) -> None:
    client = aioredis.from_url(str(idempotency_settings.redis_url), decode_responses=True)
    try:
        await client.flushdb()
        store = IdempotencyStore(client, idempotency_settings)

        assert await store.begin("scope", "key-2") is None

        with pytest.raises(ConflictError, match="in progress"):
            await store.begin("scope", "key-2")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_abort_clears_processing_marker(idempotency_settings: Settings) -> None:
    client = aioredis.from_url(str(idempotency_settings.redis_url), decode_responses=True)
    try:
        await client.flushdb()
        store = IdempotencyStore(client, idempotency_settings)

        assert await store.begin("scope", "key-3") is None
        await store.abort("scope", "key-3")

        assert await store.begin("scope", "key-3") is None
    finally:
        await client.aclose()
