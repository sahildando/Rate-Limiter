"""Integration tests for authentication."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.user import User
from app.tests.conftest import make_expired_token


@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient, user_credentials: dict[str, str]) -> None:
    register = await client.post("/api/v1/auth/register", json=user_credentials)
    assert register.status_code == 201
    body = register.json()
    assert body["email"] == user_credentials["email"]
    assert body["role"] == "USER"
    assert body["is_active"] is True
    assert "id" in body

    login = await client.post("/api/v1/auth/login", json=user_credentials)
    assert login.status_code == 200
    token_body = login.json()
    assert token_body["token_type"] == "bearer"
    assert token_body["access_token"]


@pytest.mark.asyncio
async def test_get_me(
    client: AsyncClient,
    auth_headers: dict[str, str],
    registered_user: dict,
) -> None:
    response = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == registered_user["email"]
    assert body["id"] == registered_user["id"]


@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient, registered_user: dict) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "securepassword123"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, registered_user: dict) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": registered_user["email"], "password": "securepassword123"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_me_without_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "NOT_AUTHENTICATED"


@pytest.mark.asyncio
async def test_me_with_expired_token(
    client: AsyncClient,
    registered_user: dict,
    settings: Settings,
) -> None:
    token = make_expired_token(settings, user_id=uuid.UUID(registered_user["id"]))
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_EXPIRED"


@pytest.mark.asyncio
async def test_login_inactive_user(
    client: AsyncClient,
    inactive_user: User,
) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": inactive_user.email, "password": "securepassword123"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INACTIVE_USER"


@pytest.mark.asyncio
async def test_me_inactive_user_with_valid_token(
    client: AsyncClient,
    inactive_user: User,
    settings: Settings,
    db_session: AsyncSession,
) -> None:
    from app.core.security import create_access_token

    token = create_access_token(
        subject=str(inactive_user.id),
        role=inactive_user.role.value,
        settings=settings,
    )
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INACTIVE_USER"
