"""Shared FastAPI dependencies."""

import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

import jwt
import redis.asyncio as aioredis
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthenticationError
from app.core.idempotency import IdempotencyStore
from app.core.redis import async_redis_client
from app.core.security import decode_access_token
from app.db.session import get_db_session
from app.models.user import User, UserRole
from app.monitoring.checker import HttpChecker
from app.repositories.user_repository import UserRepository
from app.services.analytics_service import AnalyticsService
from app.services.auth_service import AuthService
from app.services.monitor_service import MonitorService
from app.services.monitoring_service import MonitoringService

__all__ = [
    "get_analytics_service",
    "get_auth_service",
    "get_current_user",
    "get_db_session",
    "get_http_checker",
    "get_idempotency_store",
    "get_monitor_service",
    "get_monitoring_service",
    "get_redis_client",
    "get_settings_dep",
    "require_admin",
]

bearer_scheme = HTTPBearer(auto_error=False)


async def get_settings_dep() -> Settings:
    """Expose settings as a FastAPI dependency."""
    return get_settings()


async def get_redis_client() -> AsyncGenerator[aioredis.Redis, None]:
    """Yield a Redis client for the current request."""
    settings = get_settings()
    client = async_redis_client(settings)
    try:
        yield client
    finally:
        await client.aclose()


async def get_idempotency_store(
    redis_client: aioredis.Redis = Depends(get_redis_client),
    settings: Settings = Depends(get_settings_dep),
) -> IdempotencyStore:
    """Provide an IdempotencyStore bound to the current request Redis client."""
    return IdempotencyStore(redis_client, settings)


async def get_auth_service(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings_dep),
) -> AuthService:
    """Provide an AuthService bound to the current request session."""
    return AuthService(session, settings)


async def get_monitor_service(
    session: AsyncSession = Depends(get_db_session),
) -> MonitorService:
    """Provide a MonitorService bound to the current request session."""
    return MonitorService(session)


async def get_analytics_service(
    session: AsyncSession = Depends(get_db_session),
) -> AnalyticsService:
    """Provide an AnalyticsService bound to the current request session."""
    return AnalyticsService(session)


_http_checker: HttpChecker | None = None


def get_http_checker() -> HttpChecker:
    """Return the shared HTTP checker instance."""
    global _http_checker
    if _http_checker is None:
        _http_checker = HttpChecker()
    return _http_checker


async def get_monitoring_service(
    session: AsyncSession = Depends(get_db_session),
    checker: HttpChecker = Depends(get_http_checker),
) -> MonitoringService:
    """Provide a MonitoringService bound to the current request session."""
    return MonitoringService(session, checker)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings_dep),
) -> User:
    """Resolve and return the authenticated user from a Bearer JWT."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError(
            "Missing or invalid authorization header",
            code="NOT_AUTHENTICATED",
        )

    try:
        payload = decode_access_token(credentials.credentials, settings)
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Token has expired", code="TOKEN_EXPIRED") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Invalid token", code="INVALID_TOKEN") from exc

    subject = payload.get("sub")
    if not subject:
        raise AuthenticationError("Invalid token payload", code="INVALID_TOKEN")

    try:
        user_id = uuid.UUID(subject)
    except ValueError as exc:
        raise AuthenticationError("Invalid token subject", code="INVALID_TOKEN") from exc

    user = await UserRepository(session).get_by_id(user_id)
    if user is None:
        raise AuthenticationError("User not found", code="USER_NOT_FOUND")

    if not user.is_active:
        raise AuthenticationError("User account is inactive", code="INACTIVE_USER")

    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require the current user to have the ADMIN role."""
    if current_user.role != UserRole.ADMIN:
        from app.core.exceptions import AuthorizationError

        raise AuthorizationError("Admin access required", code="ADMIN_REQUIRED")
    return current_user


# Re-export for convenience
DbSession = AsyncSession
