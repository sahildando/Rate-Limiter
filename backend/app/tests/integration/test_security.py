"""Integration tests for Phase 6 security features."""

from unittest.mock import patch

import httpx
import pytest
from httpx import AsyncClient

from app.api.dependencies import get_http_checker
from app.core.config import Settings
from app.monitoring.checker import HttpChecker

MONITOR_PAYLOAD = {
    "name": "Payment API",
    "url": "https://example.com/health",
    "interval": 60,
    "timeout": 5000,
}


@pytest.mark.asyncio
async def test_create_monitor_blocks_ssrf_url(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.post(
        "/api/v1/monitors",
        json={**MONITOR_PAYLOAD, "url": "http://127.0.0.1/health"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "SSRF_BLOCKED"


@pytest.mark.asyncio
async def test_idempotent_manual_check_returns_same_response(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    create = await client.post("/api/v1/monitors", json=MONITOR_PAYLOAD, headers=auth_headers)
    monitor_id = create.json()["id"]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200)

    checker = HttpChecker(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    client.app.dependency_overrides[get_http_checker] = lambda: checker

    try:
        headers = {**auth_headers, "Idempotency-Key": "manual-check-1"}
        first = await client.post(
            f"/api/v1/monitors/{monitor_id}/check",
            headers=headers,
        )
        second = await client.post(
            f"/api/v1/monitors/{monitor_id}/check",
            headers=headers,
        )

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["id"] == second.json()["id"]
    finally:
        client.app.dependency_overrides.pop(get_http_checker, None)
        await checker.aclose()


@pytest.mark.asyncio
async def test_rate_limit_returns_429(
    client: AsyncClient,
    settings: Settings,
) -> None:
    limited_settings = Settings(
        environment=settings.environment,
        database_url=settings.database_url,
        redis_url=settings.redis_url,
        jwt_secret=settings.jwt_secret,
        rate_limit_anonymous_per_minute=2,
        rate_limit_authenticated_per_minute=2,
        rate_limit_login_per_minute=2,
    )

    with patch("app.core.rate_limiter.get_settings", return_value=limited_settings):
        for _ in range(2):
            response = await client.get("/api/v1/monitors")
            assert response.status_code == 401

        blocked = await client.get("/api/v1/monitors")
        assert blocked.status_code == 429
        assert blocked.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
