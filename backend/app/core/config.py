"""Application configuration via environment variables."""

from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, PostgresDsn, RedisDsn, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.database import (
    asyncpg_connect_args,
    normalize_async_database_url,
    strip_unsupported_query_params,
)

_INSECURE_JWT_SECRETS = frozenset(
    {
        "change-me-in-production",
        "change-me-in-production-use-a-long-random-string",
        "test-secret-key-for-jwt-signing",
    }
)


class Settings(BaseSettings):
    """Centralized application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Literal["development", "staging", "production", "test"] = "development"
    log_level: str = "INFO"
    enable_api_docs: bool | None = Field(default=None)

    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://monitoring:monitoring@localhost:5432/monitoring"
    )
    redis_url: RedisDsn = Field(default="redis://localhost:6379/0")

    celery_broker_url: str | None = Field(default=None)
    celery_result_backend: str | None = Field(default=None)

    scheduler_poll_interval_seconds: int = Field(default=5, ge=1, le=300)
    scheduler_batch_size: int = Field(default=100, ge=1, le=1000)
    monitor_lock_ttl_seconds: int = Field(default=120, ge=10, le=600)
    monitor_pending_ttl_seconds: int = Field(default=120, ge=10, le=600)

    monitor_retry_max_attempts: int = Field(default=3, ge=1, le=10)
    monitor_retry_base_delay_seconds: float = Field(default=1.0, ge=0.1, le=60.0)
    monitor_retry_max_delay_seconds: float = Field(default=30.0, ge=1.0, le=300.0)
    monitor_failure_threshold: int = Field(default=3, ge=1, le=20)

    rate_limit_anonymous_per_minute: int = Field(default=10, ge=1, le=10000)
    rate_limit_authenticated_per_minute: int = Field(default=100, ge=1, le=10000)
    rate_limit_login_per_minute: int = Field(default=5, ge=1, le=1000)
    idempotency_ttl_seconds: int = Field(default=86400, ge=60, le=604800)

    jwt_secret: str = Field(default="change-me-in-production")
    jwt_access_token_expire_minutes: int = 30

    cors_origins: str = "http://localhost:3000"
    frontend_url: str | None = Field(default=None)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> str:
        if isinstance(value, list):
            return ",".join(value)
        return value

    @model_validator(mode="after")
    def validate_production_settings(self) -> Self:
        if self.environment != "production":
            return self

        errors: list[str] = []
        if self.jwt_secret in _INSECURE_JWT_SECRETS or len(self.jwt_secret) < 32:
            errors.append(
                "JWT_SECRET must be a secure value with at least 32 characters in production"
            )

        database = str(self.database_url).lower()
        if "localhost" in database or "127.0.0.1" in database:
            errors.append("DATABASE_URL must not point to localhost in production")

        redis = str(self.redis_url).lower()
        if "localhost" in redis or "127.0.0.1" in redis:
            errors.append("REDIS_URL must not point to localhost in production")

        if not self.cors_origins or "localhost" in self.cors_origins.lower():
            errors.append("CORS_ORIGINS must be set to the production frontend URL(s)")

        if errors:
            raise ValueError("; ".join(errors))
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_test(self) -> bool:
        return self.environment == "test"

    @property
    def api_docs_enabled(self) -> bool:
        if self.enable_api_docs is not None:
            return self.enable_api_docs
        return self.environment != "production"

    @property
    def async_database_url(self) -> str:
        return strip_unsupported_query_params(normalize_async_database_url(str(self.database_url)))

    @property
    def database_connect_args(self) -> dict[str, object]:
        return asyncpg_connect_args(str(self.database_url))

    @property
    def resolved_celery_broker_url(self) -> str:
        return self.celery_broker_url or str(self.redis_url)

    @property
    def resolved_celery_result_backend(self) -> str:
        return self.celery_result_backend or str(self.redis_url)


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
