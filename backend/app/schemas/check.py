"""Check API schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.check import CheckErrorType


class CheckResponse(BaseModel):
    """Single monitor check result."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    monitor_id: uuid.UUID
    status_code: int | None
    response_time_ms: int | None
    success: bool
    error_type: CheckErrorType | None
    error_message: str | None
    attempt_number: int
    checked_at: datetime


class CheckListResponse(BaseModel):
    """Cursor-paginated check history."""

    items: list[CheckResponse]
    next_cursor: str | None = None
    limit: int
