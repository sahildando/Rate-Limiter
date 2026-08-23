"""Monitor ORM model."""

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
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from app.models.check import Check
    from app.models.user import User


class MonitorStatus(enum.StrEnum):
    UP = "UP"
    DOWN = "DOWN"
    PENDING = "PENDING"
    UNKNOWN = "UNKNOWN"


class HttpMethod(enum.StrEnum):
    GET = "GET"
    HEAD = "HEAD"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class Monitor(TimestampMixin, Base):
    """HTTP endpoint monitor owned by a user."""

    __tablename__ = "monitors"
    __table_args__ = (
        # Supports listing monitors per user (dashboard, CRUD).
        Index("monitors_user_id_idx", "user_id"),
        # Supports scheduler queries filtering enabled monitors.
        Index("monitors_enabled_idx", "enabled"),
        # Supports scheduler polling for monitors due for execution.
        Index("monitors_next_check_idx", "enabled", "next_check_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    method: Mapped[HttpMethod] = mapped_column(
        Enum(HttpMethod, name="http_method", native_enum=False),
        nullable=False,
        default=HttpMethod.GET,
    )
    expected_status_code: Mapped[int] = mapped_column(Integer, nullable=False, default=200)
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    timeout_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=5000)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[MonitorStatus] = mapped_column(
        Enum(MonitorStatus, name="monitor_status", native_enum=False),
        nullable=False,
        default=MonitorStatus.PENDING,
    )
    last_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consecutive_failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="monitors")
    checks: Mapped[list["Check"]] = relationship(
        "Check",
        back_populates="monitor",
        cascade="all, delete-orphan",
    )
