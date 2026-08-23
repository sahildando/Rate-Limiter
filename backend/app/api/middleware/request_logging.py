"""HTTP request logging and metrics middleware."""

import time
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.metrics import record_http_request

logger = structlog.get_logger(__name__)

_OBSERVABILITY_PATHS = frozenset({"/health/live", "/health/ready", "/metrics"})


def _metric_path(path: str) -> str:
    """Normalize dynamic path segments for lower-cardinality metrics."""
    if path.startswith("/api/v1/monitors/") and path.count("/") >= 4:
        suffix = path.split("/", 4)[-1]
        if suffix in {"check", "checks", "stats"}:
            return f"/api/v1/monitors/{{id}}/{suffix}"
        if suffix and "/" not in suffix:
            return "/api/v1/monitors/{id}"
    return path


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log completed HTTP requests and record Prometheus metrics."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.url.path in _OBSERVABILITY_PATHS:
            return await call_next(request)

        started = time.perf_counter()
        response = await call_next(request)
        duration_seconds = time.perf_counter() - started
        metric_path = _metric_path(request.url.path)

        record_http_request(
            method=request.method,
            path=metric_path,
            status_code=response.status_code,
            duration_seconds=duration_seconds,
        )

        logger.info(
            "http_request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_seconds * 1000, 2),
        )
        return response
