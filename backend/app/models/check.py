"""Check ORM model."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Text,
    desc,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, generate_uuid

if TYPE_CHECKING:
    from app.models.monitor import Monitor


class CheckErrorType(enum.StrEnum):
    TIMEOUT = "TIMEOUT"
    CONNECTION = "CONNECTION"
    DNS = "DNS"
    SSL = "SSL"
    STATUS_CODE = "STATUS_CODE"
    INVALID_URL = "INVALID_URL"
    UNKNOWN = "UNKNOWN"


class Check(Base):
    """Historical record of a single monitor check execution."""

    __tablename__ = "checks"
    __table_args__ = (
        # Supports paginated check history ordered by most recent first per monitor.
        Index(
            "checks_monitor_id_checked_at_idx",
            "monitor_id",
            desc("checked_at"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    monitor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("monitors.id", ondelete="CASCADE"),
        nullable=False,
    )
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_type: Mapped[CheckErrorType | None] = mapped_column(
        Enum(CheckErrorType, name="check_error_type", native_enum=False),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    monitor: Mapped["Monitor"] = relationship("Monitor", back_populates="checks")
