"""Dashboard analytics API endpoints."""

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_analytics_service, get_current_user
from app.models.user import User
from app.schemas.stats import DashboardSummaryResponse, StatsPeriod
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "/summary",
    response_model=DashboardSummaryResponse,
    summary="Get dashboard summary",
    responses={
        200: {"description": "Aggregated dashboard statistics"},
        401: {"description": "Not authenticated"},
    },
)
async def get_dashboard_summary(
    period: StatsPeriod = Query(default=StatsPeriod.HOURS_24),
    current_user: User = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
) -> DashboardSummaryResponse:
    """Return uptime and latency summary across all monitors owned by the user."""
    return await analytics_service.get_dashboard_summary(current_user, period)
