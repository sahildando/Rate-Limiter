"""Prometheus metrics for the monitoring platform."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

from app.monitoring.checker import CheckOutcome

MONITOR_CHECKS_TOTAL = Counter(
    "monitor_checks_total",
    "Total monitor check attempts executed",
    ["source", "result"],
)

MONITOR_CHECK_ERRORS_TOTAL = Counter(
    "monitor_check_errors_total",
    "Monitor check failures by error type",
    ["error_type"],
)

MONITOR_CHECK_LATENCY_MS = Histogram(
    "monitor_check_latency_ms",
    "Monitor check latency in milliseconds",
    buckets=(25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000),
)

WORKER_TASK_FAILURES_TOTAL = Counter(
    "worker_task_failures_total",
    "Celery monitor check task failures",
)

WORKER_TASK_SKIPPED_TOTAL = Counter(
    "worker_task_skipped_total",
    "Celery monitor check tasks skipped",
    ["reason"],
)

CELERY_QUEUE_DEPTH = Gauge(
    "celery_queue_depth",
    "Pending tasks in the monitoring Celery queue",
)

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests handled by the API",
    ["method", "path", "status_code"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)


def record_check_outcome(outcome: CheckOutcome, *, source: str) -> None:
    """Record metrics for a single persisted check attempt."""
    result = "success" if outcome.success else "failure"
    MONITOR_CHECKS_TOTAL.labels(source=source, result=result).inc()

    if outcome.error_type is not None:
        MONITOR_CHECK_ERRORS_TOTAL.labels(error_type=outcome.error_type.value).inc()

    if outcome.success and outcome.response_time_ms is not None:
        MONITOR_CHECK_LATENCY_MS.observe(outcome.response_time_ms)


def record_worker_failure() -> None:
    """Record a Celery worker task failure."""
    WORKER_TASK_FAILURES_TOTAL.inc()


def record_worker_skipped(*, reason: str) -> None:
    """Record a skipped Celery task."""
    WORKER_TASK_SKIPPED_TOTAL.labels(reason=reason).inc()


def set_queue_depth(depth: int) -> None:
    """Update the Celery queue depth gauge."""
    CELERY_QUEUE_DEPTH.set(depth)


def record_http_request(
    *,
    method: str,
    path: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    """Record HTTP request metrics."""
    HTTP_REQUESTS_TOTAL.labels(
        method=method,
        path=path,
        status_code=str(status_code),
    ).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(duration_seconds)
