"""Integration tests for analytics APIs."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.check import Check
from app.models.monitor import MonitorStatus
from app.repositories.check_repository import CheckRepository
from app.repositories.monitor_repository import MonitorRepository

MONITOR_PAYLOAD = {
    "name": "Payment API",
    "url": "https://example.com/health",
    "interval": 60,
    "timeout": 5000,
}


@pytest.mark.asyncio
async def test_monitor_stats_returns_aggregated_values(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    create = await client.post(
        "/api/v1/monitors",
        json={**MONITOR_PAYLOAD, "name": "Owned Monitor"},
        headers=auth_headers,
    )
    assert create.status_code == 201
    monitor_id = create.json()["id"]
    now = datetime.now(UTC)
    repo = CheckRepository(db_session)
    for offset_minutes, latency, success in [
        (30, 100, True),
        (20, 200, True),
        (10, 300, True),
        (5, None, False),
    ]:
        await repo.create(
            Check(
                monitor_id=uuid.UUID(monitor_id),
                success=success,
                status_code=200 if success else 503,
                response_time_ms=latency,
                checked_at=now - timedelta(minutes=offset_minutes),
            )
        )
    await db_session.commit()

    response = await client.get(
        f"/api/v1/monitors/{monitor_id}/stats?period=1h",
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["period"] == "1h"
    assert body["total_checks"] == 4
    assert body["successful_checks"] == 3
    assert body["uptime_percentage"] == 75.0
    assert body["latency_ms"]["latest"] == 300
    assert body["latency_ms"]["min"] == 100
    assert body["latency_ms"]["max"] == 300
    assert body["latency_ms"]["avg"] == 200.0
    assert body["latency_ms"]["p95"] == 290.0
    assert "from" in body
    assert "to" in body


@pytest.mark.asyncio
async def test_monitor_stats_excludes_checks_outside_period(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    create = await client.post("/api/v1/monitors", json=MONITOR_PAYLOAD, headers=auth_headers)
    monitor_id = uuid.UUID(create.json()["id"])
    now = datetime.now(UTC)
    repo = CheckRepository(db_session)

    await repo.create(
        Check(
            monitor_id=monitor_id,
            success=True,
            status_code=200,
            response_time_ms=100,
            checked_at=now - timedelta(minutes=30),
        )
    )
    await repo.create(
        Check(
            monitor_id=monitor_id,
            success=True,
            status_code=200,
            response_time_ms=500,
            checked_at=now - timedelta(hours=2),
        )
    )
    await db_session.commit()

    response = await client.get(
        f"/api/v1/monitors/{monitor_id}/stats?period=1h",
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_checks"] == 1
    assert body["latency_ms"]["latest"] == 100


@pytest.mark.asyncio
async def test_monitor_stats_requires_ownership(
    client: AsyncClient,
    auth_headers: dict[str, str],
    second_user: dict,
    db_session: AsyncSession,
) -> None:
    create = await client.post("/api/v1/monitors", json=MONITOR_PAYLOAD, headers=auth_headers)
    monitor_id = create.json()["id"]

    response = await client.get(
        f"/api/v1/monitors/{monitor_id}/stats",
        headers=second_user["headers"],
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "MONITOR_NOT_FOUND"


@pytest.mark.asyncio
async def test_dashboard_summary_aggregates_user_monitors(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    up_monitor = await client.post(
        "/api/v1/monitors",
        json={**MONITOR_PAYLOAD, "name": "Up Monitor"},
        headers=auth_headers,
    )
    down_monitor = await client.post(
        "/api/v1/monitors",
        json={**MONITOR_PAYLOAD, "name": "Down Monitor", "url": "https://example.org/health"},
        headers=auth_headers,
    )
    up_id = uuid.UUID(up_monitor.json()["id"])
    down_id = uuid.UUID(down_monitor.json()["id"])

    up_entity = await MonitorRepository(db_session).get_by_id(up_id)
    down_entity = await MonitorRepository(db_session).get_by_id(down_id)
    assert up_entity is not None and down_entity is not None
    up_entity.status = MonitorStatus.UP
    down_entity.status = MonitorStatus.DOWN

    now = datetime.now(UTC)
    repo = CheckRepository(db_session)
    for monitor_id, latency in [(up_id, 100), (up_id, 200), (down_id, 300)]:
        await repo.create(
            Check(
                monitor_id=monitor_id,
                success=True,
                status_code=200,
                response_time_ms=latency,
                checked_at=now - timedelta(minutes=15),
            )
        )
    await repo.create(
        Check(
            monitor_id=down_id,
            success=False,
            status_code=503,
            response_time_ms=None,
            checked_at=now - timedelta(minutes=10),
        )
    )
    await db_session.commit()

    response = await client.get("/api/v1/dashboard/summary?period=24h", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_monitors"] == 2
    assert body["up_monitors"] == 1
    assert body["down_monitors"] == 1
    assert body["overall_uptime_percentage"] == 75.0
    assert body["average_latency_ms"] == 200.0
