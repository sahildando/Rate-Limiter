"""Shared pytest fixtures."""

import os
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
import redis.asyncio as aioredis
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.dependencies import get_db_session
from app.core.config import Settings, get_settings
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import dispose_engine
from app.main import create_app
from app.models.user import User
from app.repositories.user_repository import UserRepository

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://monitoring:monitoring@localhost:5433/monitoring_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6380/1")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-jwt-signing")
os.environ.setdefault("RATE_LIMIT_ANONYMOUS_PER_MINUTE", "10000")
os.environ.setdefault("RATE_LIMIT_AUTHENTICATED_PER_MINUTE", "10000")
os.environ.setdefault("RATE_LIMIT_LOGIN_PER_MINUTE", "1000")


@pytest.fixture(scope="session")
def settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()


@pytest_asyncio.fixture(autouse=True)
async def flush_redis(settings: Settings) -> AsyncGenerator[None, None]:
    """Clear Redis keys between tests to avoid rate-limit and idempotency bleed."""
    client = aioredis.from_url(str(settings.redis_url), decode_responses=True)
    try:
        await client.flushdb()
    finally:
        await client.aclose()
    yield
    client = aioredis.from_url(str(settings.redis_url), decode_responses=True)
    try:
        await client.flushdb()
    finally:
        await client.aclose()


@pytest_asyncio.fixture
async def db_engine(settings: Settings):
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()
    await dispose_engine()


@pytest_asyncio.fixture
async def client(db_engine) -> AsyncGenerator[AsyncClient, None]:
    session_factory = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app = create_app()
    app.dependency_overrides[get_db_session] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.app = app  # type: ignore[attr-defined]
        yield ac
    app.dependency_overrides.clear()
    await dispose_engine()
    get_settings.cache_clear()


@pytest.fixture
def user_credentials() -> dict[str, str]:
    suffix = uuid.uuid4().hex[:8]
    return {
        "email": f"user-{suffix}@example.com",
        "password": "securepassword123",
    }


@pytest_asyncio.fixture
async def registered_user(client: AsyncClient, user_credentials: dict[str, str]) -> dict:
    response = await client.post("/api/v1/auth/register", json=user_credentials)
    assert response.status_code == 201
    return {**user_credentials, **response.json()}


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient, registered_user: dict) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        },
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def second_user(client: AsyncClient) -> dict:
    credentials = {
        "email": f"other-{uuid.uuid4().hex[:8]}@example.com",
        "password": "securepassword123",
    }
    response = await client.post("/api/v1/auth/register", json=credentials)
    assert response.status_code == 201
    login = await client.post("/api/v1/auth/login", json=credentials)
    assert login.status_code == 200
    return {
        **credentials,
        "token": login.json()["access_token"],
        "headers": {"Authorization": f"Bearer {login.json()['access_token']}"},
    }


@pytest_asyncio.fixture
async def inactive_user(db_session: AsyncSession, settings: Settings) -> User:
    repo = UserRepository(db_session)
    user = await repo.create(
        email=f"inactive-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("securepassword123"),
    )
    user.is_active = False
    await db_session.commit()
    await db_session.refresh(user)
    return user


def make_expired_token(settings: Settings, *, user_id: uuid.UUID, role: str = "USER") -> str:
    """Create a JWT that is already expired."""
    settings_copy = Settings(
        environment=settings.environment,
        database_url=settings.database_url,
        redis_url=settings.redis_url,
        jwt_secret=settings.jwt_secret,
        jwt_access_token_expire_minutes=-1,
    )
    return create_access_token(subject=str(user_id), role=role, settings=settings_copy)
