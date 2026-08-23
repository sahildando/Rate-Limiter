"""Health check API endpoints."""

from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session, get_redis_client

router = APIRouter(tags=["health"])


@router.get(
    "/health/live",
    summary="Liveness probe",
    description="Returns 200 when the application process is running. Does not check dependencies.",
    responses={
        200: {"description": "Application is alive"},
    },
)
async def liveness() -> dict[str, str]:
    """Indicate that the API process is alive."""
    return {"status": "alive"}


@router.get(
    "/health/ready",
    summary="Readiness probe",
    description="Verifies required dependencies (PostgreSQL, Redis) are reachable.",
    responses={
        200: {"description": "All dependencies are available"},
        503: {"description": "One or more dependencies are unavailable"},
    },
)
async def readiness(
    db: AsyncSession = Depends(get_db_session),
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> JSONResponse:
    """Verify database and Redis connectivity before accepting traffic."""
    checks: dict[str, str] = {}
    all_healthy = True

    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "unavailable"
        all_healthy = False

    try:
        await redis_client.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "unavailable"
        all_healthy = False

    body: dict[str, Any] = {
        "status": "ready" if all_healthy else "not_ready",
        "checks": checks,
    }
    return JSONResponse(
        status_code=status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        content=body,
    )
