"""Integration tests for monitor authorization."""

import pytest
from httpx import AsyncClient

MONITOR_PAYLOAD = {
    "name": "Payment API",
    "url": "https://example.com/health",
    "interval": 60,
    "timeout": 5000,
}


@pytest.mark.asyncio
async def test_create_and_get_monitor(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    create = await client.post("/api/v1/monitors", json=MONITOR_PAYLOAD, headers=auth_headers)
    assert create.status_code == 201
    monitor = create.json()
    assert monitor["name"] == MONITOR_PAYLOAD["name"]
    assert monitor["url"] == MONITOR_PAYLOAD["url"]
    assert monitor["interval"] == 60
    assert monitor["timeout"] == 5000
    assert monitor["status"] == "PENDING"

    get = await client.get(f"/api/v1/monitors/{monitor['id']}", headers=auth_headers)
    assert get.status_code == 200
    assert get.json()["id"] == monitor["id"]


@pytest.mark.asyncio
async def test_list_monitors(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    await client.post("/api/v1/monitors", json=MONITOR_PAYLOAD, headers=auth_headers)
    response = await client.get("/api/v1/monitors", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert len(body["items"]) >= 1


@pytest.mark.asyncio
async def test_update_monitor(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    create = await client.post("/api/v1/monitors", json=MONITOR_PAYLOAD, headers=auth_headers)
    monitor_id = create.json()["id"]

    update = await client.patch(
        f"/api/v1/monitors/{monitor_id}",
        json={"name": "Updated API"},
        headers=auth_headers,
    )
    assert update.status_code == 200
    assert update.json()["name"] == "Updated API"


@pytest.mark.asyncio
async def test_delete_monitor(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    create = await client.post("/api/v1/monitors", json=MONITOR_PAYLOAD, headers=auth_headers)
    monitor_id = create.json()["id"]

    delete = await client.delete(f"/api/v1/monitors/{monitor_id}", headers=auth_headers)
    assert delete.status_code == 204

    get = await client.get(f"/api/v1/monitors/{monitor_id}", headers=auth_headers)
    assert get.status_code == 404


@pytest.mark.asyncio
async def test_monitors_require_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/monitors")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_cross_user_monitor_access_denied(
    client: AsyncClient,
    auth_headers: dict[str, str],
    second_user: dict,
) -> None:
    create = await client.post("/api/v1/monitors", json=MONITOR_PAYLOAD, headers=auth_headers)
    monitor_id = create.json()["id"]

    get = await client.get(f"/api/v1/monitors/{monitor_id}", headers=second_user["headers"])
    assert get.status_code == 404
    assert get.json()["error"]["code"] == "MONITOR_NOT_FOUND"

    patch = await client.patch(
        f"/api/v1/monitors/{monitor_id}",
        json={"name": "Hijacked"},
        headers=second_user["headers"],
    )
    assert patch.status_code == 404

    delete = await client.delete(f"/api/v1/monitors/{monitor_id}", headers=second_user["headers"])
    assert delete.status_code == 404

    # Original owner still has access
    owner_get = await client.get(f"/api/v1/monitors/{monitor_id}", headers=auth_headers)
    assert owner_get.status_code == 200


@pytest.mark.asyncio
async def test_cross_user_cannot_see_others_monitors_in_list(
    client: AsyncClient,
    auth_headers: dict[str, str],
    second_user: dict,
) -> None:
    await client.post("/api/v1/monitors", json=MONITOR_PAYLOAD, headers=auth_headers)

    other_list = await client.get("/api/v1/monitors", headers=second_user["headers"])
    assert other_list.status_code == 200
    assert other_list.json()["total"] == 0
    assert other_list.json()["items"] == []
