"""Integration tests for health endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_liveness_always_returns_200(client: AsyncClient) -> None:
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


@pytest.mark.asyncio
async def test_readiness_returns_dependency_status(client: AsyncClient) -> None:
    response = await client.get("/health/ready")
    body = response.json()

    assert "status" in body
    assert "checks" in body
    assert "database" in body["checks"]
    assert "redis" in body["checks"]
    assert response.status_code in (200, 503)
