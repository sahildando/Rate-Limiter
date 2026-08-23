"""Unit tests for configuration."""

from app.core.config import Settings, get_settings


def test_settings_defaults() -> None:
    settings = Settings(
        environment="test",
        database_url="postgresql+asyncpg://user:pass@localhost/db",
        redis_url="redis://localhost:6379/0",
    )
    assert settings.environment == "test"
    assert settings.is_test is True
    assert settings.jwt_access_token_expire_minutes == 30


def test_cors_origins_parsing() -> None:
    settings = Settings(
        environment="test",
        database_url="postgresql+asyncpg://user:pass@localhost/db",
        redis_url="redis://localhost:6379/0",
        cors_origins="http://localhost:3000, http://127.0.0.1:3000",
    )
    assert settings.cors_origins_list == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


def test_get_settings_cached() -> None:
    get_settings.cache_clear()
    first = get_settings()
    second = get_settings()
    assert first is second
