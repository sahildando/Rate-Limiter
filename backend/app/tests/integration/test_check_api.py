"""Integration tests for manual check API endpoint."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import AsyncClient

from app.api.dependencies import get_http_checker
from app.monitoring.checker import HttpChecker

MONITOR_PAYLOAD = {
    "name": "Payment API",
    "url": "https://example.com/health",
    "interval": 60,
    "timeout": 5000,
}


@pytest.mark.asyncio
async def test_trigger_check_success(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    create = await client.post("/api/v1/monitors", json=MONITOR_PAYLOAD, headers=auth_headers)
    monitor_id = create.json()["id"]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200)

    checker = HttpChecker(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    client.app.dependency_overrides[get_http_checker] = lambda: checker

    try:
        response = await client.post(
            f"/api/v1/monitors/{monitor_id}/check",
            headers=auth_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["status_code"] == 200
        assert body["response_time_ms"] is not None

        monitor = await client.get(f"/api/v1/monitors/{monitor_id}", headers=auth_headers)
        assert monitor.json()["status"] == "UP"
        assert monitor.json()["latency_ms"] == body["response_time_ms"]
    finally:
        client.app.dependency_overrides.pop(get_http_checker, None)
        await checker.aclose()


@pytest.mark.asyncio
async def test_trigger_check_failure(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    create = await client.post("/api/v1/monitors", json=MONITOR_PAYLOAD, headers=auth_headers)
    monitor_id = create.json()["id"]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    checker = HttpChecker(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    client.app.dependency_overrides[get_http_checker] = lambda: checker

    try:
        with patch("app.services.monitoring_service.asyncio.sleep", new=AsyncMock()):
            response = await client.post(
                f"/api/v1/monitors/{monitor_id}/check",
                headers=auth_headers,
            )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is False
        assert body["error_type"] == "STATUS_CODE"
    finally:
        client.app.dependency_overrides.pop(get_http_checker, None)
        await checker.aclose()


@pytest.mark.asyncio
async def test_list_checks_after_manual_check(
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
        await client.post(f"/api/v1/monitors/{monitor_id}/check", headers=auth_headers)

        response = await client.get(
            f"/api/v1/monitors/{monitor_id}/checks",
            headers=auth_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body["items"]) == 1
        assert body["items"][0]["success"] is True
        assert body["limit"] == 50
    finally:
        client.app.dependency_overrides.pop(get_http_checker, None)
        await checker.aclose()


@pytest.mark.asyncio
async def test_trigger_check_requires_ownership(
    client: AsyncClient,
    auth_headers: dict[str, str],
    second_user: dict,
) -> None:
    create = await client.post("/api/v1/monitors", json=MONITOR_PAYLOAD, headers=auth_headers)
    monitor_id = create.json()["id"]

    response = await client.post(
        f"/api/v1/monitors/{monitor_id}/check",
        headers=second_user["headers"],
    )
    assert response.status_code == 404
