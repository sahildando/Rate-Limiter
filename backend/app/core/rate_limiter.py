"""Redis-backed API rate limiting."""

import hashlib

import redis.asyncio as aioredis

from app.core.config import Settings, get_settings


def _hash_identifier(identifier: str) -> str:
    return hashlib.sha256(identifier.encode()).hexdigest()


class RateLimiter:
    """Fixed-window rate limiter using Redis counters."""

    def __init__(self, redis_client: aioredis.Redis, settings: Settings | None = None) -> None:
        self._redis = redis_client
        self._settings = settings or get_settings()

    async def is_allowed(self, *, key: str, limit: int, window_seconds: int = 60) -> bool:
        """Return True if the request is within the rate limit."""
        redis_key = f"ratelimit:{key}"
        count = await self._redis.incr(redis_key)
        if count == 1:
            await self._redis.expire(redis_key, window_seconds)
        return count <= limit

    async def check_request(
        self,
        *,
        client_ip: str,
        path: str,
        authorization: str | None,
    ) -> bool:
        """Apply endpoint-specific rate limits."""
        if path.startswith("/health"):
            return True

        if path.endswith("/auth/login"):
            key = f"login:{_hash_identifier(client_ip)}"
            return await self.is_allowed(
                key=key,
                limit=self._settings.rate_limit_login_per_minute,
            )

        if authorization and authorization.lower().startswith("bearer "):
            token = authorization.split(" ", 1)[1]
            key = f"auth:{_hash_identifier(token)}"
            return await self.is_allowed(
                key=key,
                limit=self._settings.rate_limit_authenticated_per_minute,
            )

        key = f"anon:{_hash_identifier(client_ip)}"
        return await self.is_allowed(
            key=key,
            limit=self._settings.rate_limit_anonymous_per_minute,
        )
