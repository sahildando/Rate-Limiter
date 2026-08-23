"""Typed aggregation results from check statistics queries."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MonitorStatsAggregation:
    """Aggregated check statistics for a single monitor."""

    total_checks: int
    successful_checks: int
    avg_latency_ms: float | None
    min_latency_ms: int | None
    max_latency_ms: int | None
    p95_latency_ms: float | None
    latest_latency_ms: int | None


@dataclass(frozen=True, slots=True)
class UserChecksAggregation:
    """Aggregated check statistics across all monitors owned by a user."""

    total_checks: int
    successful_checks: int
    average_latency_ms: float | None
