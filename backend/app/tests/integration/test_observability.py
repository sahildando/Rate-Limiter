"""Integration tests for observability features."""

import pytest
from httpx import AsyncClient

from app.api.middleware.correlation_id import CORRELATION_ID_HEADER
from app.core.metrics import MONITOR_CHECKS_TOTAL, record_check_outcome
from app.models.check import CheckErrorType
from app.monitoring.checker import CheckOutcome


@pytest.mark.asyncio
async def test_metrics_endpoint_returns_prometheus_format(client: AsyncClient) -> None:
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    body = response.text
    assert "monitor_checks_total" in body
    assert "http_requests_total" in body
    assert "celery_queue_depth" in body


@pytest.mark.asyncio
async def test_correlation_id_is_returned(client: AsyncClient) -> None:
    correlation_id = "test-correlation-12345"
    response = await client.get(
        "/health/live",
        headers={CORRELATION_ID_HEADER: correlation_id},
    )
    assert response.status_code == 200
    assert response.headers.get(CORRELATION_ID_HEADER) == correlation_id


@pytest.mark.asyncio
async def test_correlation_id_is_generated_when_missing(client: AsyncClient) -> None:
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.headers.get(CORRELATION_ID_HEADER)


def test_record_check_outcome_increments_metrics() -> None:
    before = MONITOR_CHECKS_TOTAL.labels(source="test", result="success")._value.get()  # type: ignore[attr-defined]
    record_check_outcome(
        CheckOutcome(success=True, status_code=200, response_time_ms=120),
        source="test",
    )
    after = MONITOR_CHECKS_TOTAL.labels(source="test", result="success")._value.get()  # type: ignore[attr-defined]
    assert after == before + 1

    record_check_outcome(
        CheckOutcome(
            success=False,
            status_code=None,
            response_time_ms=0,
            error_type=CheckErrorType.TIMEOUT,
            error_message="timeout",
        ),
        source="test",
    )
    failure_count = MONITOR_CHECKS_TOTAL.labels(source="test", result="failure")._value.get()  # type: ignore[attr-defined]
    assert failure_count >= 1
