"""Prometheus metrics endpoint."""

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.dependencies import get_redis_client
from app.core.metrics import set_queue_depth

router = APIRouter(tags=["observability"])

MONITORING_QUEUE_KEY = "monitoring"


@router.get(
    "/metrics",
    summary="Prometheus metrics",
    description="Expose application metrics in Prometheus text format.",
    include_in_schema=False,
)
async def metrics(
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> Response:
    """Return Prometheus metrics, including live Celery queue depth when available."""
    try:
        depth = await redis_client.llen(MONITORING_QUEUE_KEY)
        set_queue_depth(int(depth))
    except Exception:
        set_queue_depth(0)

    payload = generate_latest()
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)
