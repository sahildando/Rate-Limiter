"""Monitor request/response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.models.monitor import HttpMethod, MonitorStatus


class MonitorCreateRequest(BaseModel):
    """Payload for creating a new monitor."""

    name: str = Field(..., min_length=1, max_length=255, examples=["Payment API"])
    url: HttpUrl = Field(..., examples=["https://example.com/health"])
    method: HttpMethod = Field(default=HttpMethod.GET)
    expected_status_code: int = Field(default=200, ge=100, le=599)
    interval: int = Field(default=60, ge=10, le=86400, description="Check interval in seconds")
    timeout: int = Field(default=5000, ge=1000, le=60000, description="Timeout in milliseconds")
    enabled: bool = Field(default=True)


class MonitorUpdateRequest(BaseModel):
    """Payload for partially updating a monitor."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    url: HttpUrl | None = None
    method: HttpMethod | None = None
    expected_status_code: int | None = Field(default=None, ge=100, le=599)
    interval: int | None = Field(default=None, ge=10, le=86400)
    timeout: int | None = Field(default=None, ge=1000, le=60000)
    enabled: bool | None = None


class MonitorResponse(BaseModel):
    """Monitor resource returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    url: str
    method: HttpMethod
    expected_status_code: int
    interval: int = Field(validation_alias="interval_seconds", serialization_alias="interval")
    timeout: int = Field(validation_alias="timeout_ms", serialization_alias="timeout")
    enabled: bool
    status: MonitorStatus
    latency_ms: int | None = Field(default=None, validation_alias="last_latency_ms")
    failure_count: int
    consecutive_failure_count: int
    last_checked_at: datetime | None
    last_success_at: datetime | None
    last_failure_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MonitorListResponse(BaseModel):
    """Paginated list of monitors."""

    items: list[MonitorResponse]
    total: int
    offset: int
    limit: int
