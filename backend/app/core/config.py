"""Application configuration via environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> str:
        if isinstance(value, list):
            return ",".join(value)
        return value

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_test(self) -> bool:
        return self.environment == "test"

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
