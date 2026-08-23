"""Retry policy with exponential backoff for transient monitor check failures."""

import random
from dataclasses import dataclass

from app.models.check import CheckErrorType
from app.monitoring.checker import CheckOutcome

# HTTP status codes considered transient server-side failures.
TRANSIENT_HTTP_STATUS_CODES: frozenset[int] = frozenset({500, 502, 503, 504})

# Error types that may succeed on a subsequent attempt.
RETRYABLE_ERROR_TYPES: frozenset[CheckErrorType] = frozenset(
    {
        CheckErrorType.TIMEOUT,
        CheckErrorType.CONNECTION,
        CheckErrorType.DNS,
    }
)


@dataclass(frozen=True, slots=True)
class RetryConfig:
    """Configurable retry and failure-detection settings."""

    max_attempts: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 30.0
    failure_threshold: int = 3


def is_retryable(outcome: CheckOutcome) -> bool:
    """Return True when the check outcome warrants a retry."""
    if outcome.success:
        return False

    if outcome.error_type in RETRYABLE_ERROR_TYPES:
        return True

    if (
        outcome.error_type == CheckErrorType.STATUS_CODE
        and outcome.status_code is not None
        and outcome.status_code in TRANSIENT_HTTP_STATUS_CODES
    ):
        return True

    return False


def calculate_backoff_seconds(
    attempt: int,
    *,
    base_delay_seconds: float,
    max_delay_seconds: float,
) -> float:
    """
    Compute delay before the next retry attempt.

    Formula: min(base * 2^(attempt - 1), max_delay) with additive jitter.
    """
    if attempt < 1:
        raise ValueError("attempt must be >= 1")

    delay = min(base_delay_seconds * (2 ** (attempt - 1)), max_delay_seconds)
    jitter = random.uniform(0, delay * 0.25)
    return delay + jitter
