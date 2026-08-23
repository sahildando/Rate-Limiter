"""Unit tests for Redis-backed rate limiting."""

import pytest
import redis.asyncio as aioredis

from app.core.config import Settings
from app.core.rate_limiter import RateLimiter


@pytest.fixture
def rate_limit_settings() -> Settings:
    return Settings(
        environment="test",
        database_url="postgresql+asyncpg://monitoring:monitoring@localhost:5433/monitoring_test",
        redis_url="redis://localhost:6380/1",
        rate_limit_anonymous_per_minute=3,
        rate_limit_authenticated_per_minute=5,
        rate_limit_login_per_minute=2,
    )


@pytest.mark.asyncio
async def test_anonymous_rate_limit(rate_limit_settings: Settings) -> None:
    client = aioredis.from_url(str(rate_limit_settings.redis_url), decode_responses=True)
    try:
        await client.flushdb()
        limiter = RateLimiter(client, rate_limit_settings)

        for _ in range(3):
            assert await limiter.check_request(
                client_ip="203.0.113.1",
                path="/api/v1/auth/register",
                authorization=None,
            )

        assert not await limiter.check_request(
            client_ip="203.0.113.1",
            path="/api/v1/auth/register",
            authorization=None,
        )
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_login_rate_limit(rate_limit_settings: Settings) -> None:
    client = aioredis.from_url(str(rate_limit_settings.redis_url), decode_responses=True)
    try:
        await client.flushdb()
        limiter = RateLimiter(client, rate_limit_settings)

        for _ in range(2):
            assert await limiter.check_request(
                client_ip="203.0.113.2",
                path="/api/v1/auth/login",
                authorization=None,
            )

        assert not await limiter.check_request(
            client_ip="203.0.113.2",
            path="/api/v1/auth/login",
            authorization=None,
        )
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_health_path_skipped(rate_limit_settings: Settings) -> None:
    client = aioredis.from_url(str(rate_limit_settings.redis_url), decode_responses=True)
    try:
        await client.flushdb()
        limiter = RateLimiter(client, rate_limit_settings)

        for _ in range(20):
            assert await limiter.check_request(
                client_ip="203.0.113.3",
                path="/health/live",
                authorization=None,
            )
    finally:
        await client.aclose()
