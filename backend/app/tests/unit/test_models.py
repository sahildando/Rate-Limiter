"""Unit tests for ORM models."""

import uuid

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Check, Monitor, User, UserRole
from app.models.monitor import HttpMethod, MonitorStatus


@pytest.mark.asyncio
async def test_create_user_monitor_check(db_session: AsyncSession) -> None:
    user = User(
        email="test@example.com",
        password_hash="hashed",
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    monitor = Monitor(
        user_id=user.id,
        name="Payment API",
        url="https://example.com/health",
        method=HttpMethod.GET,
        expected_status_code=200,
        interval_seconds=60,
        timeout_ms=5000,
        enabled=True,
        status=MonitorStatus.PENDING,
    )
    db_session.add(monitor)
    await db_session.flush()

    check = Check(
        monitor_id=monitor.id,
        status_code=200,
        response_time_ms=142,
        success=True,
        attempt_number=1,
    )
    db_session.add(check)
    await db_session.commit()

    assert user.id is not None
    assert monitor.user_id == user.id
    assert check.monitor_id == monitor.id
    assert isinstance(user.id, uuid.UUID)


def test_monitor_indexes_defined() -> None:
    table = Monitor.__table__
    index_names = {index.name for index in table.indexes}
    assert "monitors_user_id_idx" in index_names
    assert "monitors_enabled_idx" in index_names
    assert "monitors_next_check_idx" in index_names


def test_check_composite_index_defined() -> None:
    table = Check.__table__
    index_names = {index.name for index in table.indexes}
    assert "checks_monitor_id_checked_at_idx" in index_names


def test_user_email_index() -> None:
    mapper = inspect(User)
    email_col = mapper.columns["email"]
    assert email_col.index is True
    assert email_col.unique is True
