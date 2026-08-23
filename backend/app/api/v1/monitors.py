"""Monitor API endpoints."""

import uuid

from fastapi import APIRouter, Depends, Header, Query, status

from app.api.dependencies import (
    get_analytics_service,
    get_current_user,
    get_idempotency_store,
    get_monitor_service,
    get_monitoring_service,
)
from app.core.idempotency import IdempotencyStore
from app.models.user import User
from app.schemas.check import CheckListResponse, CheckResponse
from app.schemas.monitor import (
    MonitorCreateRequest,
    MonitorListResponse,
    MonitorResponse,
    MonitorUpdateRequest,
)
from app.schemas.stats import MonitorStatsResponse, StatsPeriod
from app.services.analytics_service import AnalyticsService
from app.services.monitor_service import MonitorService
from app.services.monitoring_service import MonitoringService

router = APIRouter(prefix="/monitors", tags=["monitors"])


@router.post(
    "",
    response_model=MonitorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a monitor",
    responses={
        201: {"description": "Monitor created"},
        401: {"description": "Not authenticated"},
        422: {"description": "Validation error"},
    },
)
async def create_monitor(
    data: MonitorCreateRequest,
    current_user: User = Depends(get_current_user),
    monitor_service: MonitorService = Depends(get_monitor_service),
) -> MonitorResponse:
    """Create a new HTTP endpoint monitor owned by the current user."""
    return await monitor_service.create_monitor(current_user, data)


@router.get(
    "",
    response_model=MonitorListResponse,
    summary="List monitors",
    responses={
        200: {"description": "Paginated monitor list"},
        401: {"description": "Not authenticated"},
    },
)
async def list_monitors(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    monitor_service: MonitorService = Depends(get_monitor_service),
) -> MonitorListResponse:
    """List monitors owned by the current user."""
    return await monitor_service.list_monitors(current_user, offset=offset, limit=limit)


@router.get(
    "/{monitor_id}",
    response_model=MonitorResponse,
    summary="Get a monitor",
    responses={
        200: {"description": "Monitor details"},
        401: {"description": "Not authenticated"},
        404: {"description": "Monitor not found"},
    },
)
async def get_monitor(
    monitor_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    monitor_service: MonitorService = Depends(get_monitor_service),
) -> MonitorResponse:
    """Retrieve a single monitor by ID."""
    return await monitor_service.get_monitor(current_user, monitor_id)


@router.patch(
    "/{monitor_id}",
    response_model=MonitorResponse,
    summary="Update a monitor",
    responses={
        200: {"description": "Monitor updated"},
        401: {"description": "Not authenticated"},
        404: {"description": "Monitor not found"},
        422: {"description": "Validation error"},
    },
)
async def update_monitor(
    monitor_id: uuid.UUID,
    data: MonitorUpdateRequest,
    current_user: User = Depends(get_current_user),
    monitor_service: MonitorService = Depends(get_monitor_service),
) -> MonitorResponse:
    """Partially update a monitor owned by the current user."""
    return await monitor_service.update_monitor(current_user, monitor_id, data)


@router.delete(
    "/{monitor_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a monitor",
    responses={
        204: {"description": "Monitor deleted"},
        401: {"description": "Not authenticated"},
        404: {"description": "Monitor not found"},
    },
)
async def delete_monitor(
    monitor_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    monitor_service: MonitorService = Depends(get_monitor_service),
) -> None:
    """Delete a monitor owned by the current user."""
    await monitor_service.delete_monitor(current_user, monitor_id)


@router.get(
    "/{monitor_id}/stats",
    response_model=MonitorStatsResponse,
    summary="Get monitor statistics",
    responses={
        200: {"description": "Aggregated uptime and latency statistics"},
        401: {"description": "Not authenticated"},
        404: {"description": "Monitor not found"},
    },
)
async def get_monitor_stats(
    monitor_id: uuid.UUID,
    period: StatsPeriod = Query(default=StatsPeriod.HOURS_24),
    current_user: User = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
) -> MonitorStatsResponse:
    """Return uptime and latency statistics for a monitor over the selected period."""
    return await analytics_service.get_monitor_stats(current_user, monitor_id, period)


@router.post(
    "/{monitor_id}/check",
    response_model=CheckResponse,
    summary="Trigger a manual check",
    responses={
        200: {"description": "Check executed and persisted"},
        401: {"description": "Not authenticated"},
        404: {"description": "Monitor not found"},
    },
)
async def trigger_check(
    monitor_id: uuid.UUID,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: User = Depends(get_current_user),
    monitoring_service: MonitoringService = Depends(get_monitoring_service),
    idempotency_store: IdempotencyStore = Depends(get_idempotency_store),
) -> CheckResponse:
    """Execute an immediate HTTP check against the monitor target."""
    return await monitoring_service.trigger_check_for_user(
        current_user,
        monitor_id,
        idempotency_key=idempotency_key,
        idempotency_store=idempotency_store,
    )


@router.get(
    "/{monitor_id}/checks",
    response_model=CheckListResponse,
    summary="List check history",
    responses={
        200: {"description": "Paginated check history"},
        401: {"description": "Not authenticated"},
        404: {"description": "Monitor not found"},
    },
)
async def list_checks(
    monitor_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    monitoring_service: MonitoringService = Depends(get_monitoring_service),
) -> CheckListResponse:
    """Return cursor-paginated check history for a monitor."""
    return await monitoring_service.list_checks_for_user(
        current_user,
        monitor_id,
        limit=limit,
        cursor=cursor,
    )
