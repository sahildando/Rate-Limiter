"""Unit tests for security utilities."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import Settings
from app.core.security import (
    JWT_ALGORITHM,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_password() -> None:
    hashed = hash_password("securepassword123")
    assert hashed != "securepassword123"
    assert verify_password("securepassword123", hashed)
    assert not verify_password("wrongpassword", hashed)


def test_create_and_decode_access_token() -> None:
    settings = Settings(
        environment="test",
        database_url="postgresql+asyncpg://user:pass@localhost/db",
        redis_url="redis://localhost:6379/0",
        jwt_secret="test-secret",
        jwt_access_token_expire_minutes=30,
    )
    user_id = str(uuid.uuid4())
    token = create_access_token(subject=user_id, role="USER", settings=settings)
    payload = decode_access_token(token, settings)

    assert payload["sub"] == user_id
    assert payload["role"] == "USER"
    assert "iat" in payload
    assert "exp" in payload


def test_expired_token_raises() -> None:
    settings = Settings(
        environment="test",
        database_url="postgresql+asyncpg://user:pass@localhost/db",
        redis_url="redis://localhost:6379/0",
        jwt_secret="test-secret",
        jwt_access_token_expire_minutes=30,
    )
    now = datetime.now(UTC)
    payload = {
        "sub": str(uuid.uuid4()),
        "role": "USER",
        "iat": int((now - timedelta(hours=1)).timestamp()),
        "exp": int((now - timedelta(minutes=1)).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token, settings)
