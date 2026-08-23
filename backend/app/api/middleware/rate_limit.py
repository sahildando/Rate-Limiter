"""HTTP middleware."""

from collections.abc import Awaitable, Callable

import redis.asyncio as aioredis
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from app.core.config import get_settings
from app.core.rate_limiter import RateLimiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Enforce Redis-backed rate limits on incoming API requests."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._settings = get_settings()

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.url.path.startswith("/health") or request.url.path == "/metrics":
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        authorization = request.headers.get("authorization")

        redis_client = aioredis.from_url(
            str(self._settings.redis_url),
            decode_responses=True,
        )
        try:
            allowed = await RateLimiter(redis_client).check_request(
                client_ip=client_ip,
                path=request.url.path,
                authorization=authorization,
            )
        finally:
            await redis_client.aclose()

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Rate limit exceeded",
                    }
                },
            )

        return await call_next(request)
