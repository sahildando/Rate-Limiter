"""Redis connection helpers for local and production (Upstash TLS)."""

import ssl
from typing import cast

import redis
import redis.asyncio as aioredis

from app.core.config import Settings, get_settings


def redis_url_requires_ssl(redis_url: str) -> bool:
    """Return True when the Redis URL uses TLS (e.g. Upstash rediss://)."""
    return redis_url.lower().startswith("rediss://")


def redis_ssl_kwargs() -> dict[str, object]:
    """SSL options for redis-py when connecting to rediss:// URLs."""
    return {"ssl_cert_reqs": ssl.CERT_REQUIRED}


def sync_redis_client(
    settings: Settings | None = None,
    *,
    decode_responses: bool = True,
) -> redis.Redis:
    """Create a synchronous Redis client with TLS when required."""
    resolved = settings or get_settings()
    url = str(resolved.redis_url)
    kwargs: dict[str, object] = {"decode_responses": decode_responses}
    if redis_url_requires_ssl(url):
        kwargs.update(redis_ssl_kwargs())
    return cast(redis.Redis, redis.from_url(url, **kwargs))  # type: ignore[no-untyped-call]


def async_redis_client(
    settings: Settings | None = None,
    *,
    decode_responses: bool = True,
) -> aioredis.Redis:
    """Create an async Redis client with TLS when required."""
    resolved = settings or get_settings()
    url = str(resolved.redis_url)
    kwargs: dict[str, object] = {"decode_responses": decode_responses}
    if redis_url_requires_ssl(url):
        kwargs.update(redis_ssl_kwargs())
    return cast(aioredis.Redis, aioredis.from_url(url, **kwargs))  # type: ignore[no-untyped-call]


def celery_ssl_config(url: str) -> dict[str, object] | None:
    """Return Celery SSL settings for rediss:// broker/backend URLs."""
    if redis_url_requires_ssl(url):
        return redis_ssl_kwargs()
    return None
