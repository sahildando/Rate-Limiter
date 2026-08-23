"""Unit tests for Redis connection helpers."""

from app.core.redis import (
    async_redis_client,
    celery_ssl_config,
    redis_ssl_kwargs,
    redis_url_requires_ssl,
    sync_redis_client,
)


def test_redis_url_requires_ssl_for_rediss() -> None:
    assert redis_url_requires_ssl("rediss://default:pass@host.upstash.io:6379")
    assert not redis_url_requires_ssl("redis://localhost:6379/0")


def test_celery_ssl_config_for_rediss() -> None:
    config = celery_ssl_config("rediss://default:pass@host.upstash.io:6379")
    assert config is not None
    assert config == redis_ssl_kwargs()


def test_celery_ssl_config_none_for_plain_redis() -> None:
    assert celery_ssl_config("redis://localhost:6379/0") is None


def test_sync_redis_client_accepts_rediss_url() -> None:
    from app.core.config import Settings

    settings = Settings(redis_url="rediss://default:pass@host.upstash.io:6379")
    instance = sync_redis_client(settings)
    assert instance.connection_pool.connection_kwargs.get("ssl_cert_reqs") is not None
    instance.close()


def test_async_redis_client_accepts_rediss_url() -> None:
    from app.core.config import Settings

    settings = Settings(redis_url="rediss://default:pass@host.upstash.io:6379")
    instance = async_redis_client(settings)
    assert instance.connection_pool.connection_kwargs.get("ssl_cert_reqs") is not None
