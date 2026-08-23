"""Unit tests for database URL normalization."""

from app.core.database import (
    asyncpg_connect_args,
    database_requires_ssl,
    normalize_async_database_url,
    strip_unsupported_query_params,
)


def test_normalize_neon_url() -> None:
    url = "postgresql://user:pass@ep-test.neon.tech/neondb?sslmode=require"
    assert normalize_async_database_url(url) == (
        "postgresql+asyncpg://user:pass@ep-test.neon.tech/neondb?sslmode=require"
    )
    assert database_requires_ssl(url) is True
    assert asyncpg_connect_args(url) == {"ssl": True}


def test_strip_ssl_query_params() -> None:
    url = "postgresql+asyncpg://user:pass@host/db?sslmode=require&channel_binding=require"
    stripped = strip_unsupported_query_params(url)
    assert "sslmode" not in stripped
    assert "channel_binding=require" in stripped
