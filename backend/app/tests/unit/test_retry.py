"""Unit tests for retry policy and exponential backoff."""

from unittest.mock import patch

import pytest

from app.models.check import CheckErrorType
from app.monitoring.checker import CheckOutcome
from app.monitoring.retry import (
    calculate_backoff_seconds,
    is_retryable,
)


def _outcome(
    *,
    success: bool,
    error_type: CheckErrorType | None = None,
    status_code: int | None = None,
) -> CheckOutcome:
    return CheckOutcome(
        success=success,
        status_code=status_code,
        response_time_ms=100,
        error_type=error_type,
        error_message="error" if not success else None,
    )


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        (_outcome(success=True), False),
        (_outcome(success=False, error_type=CheckErrorType.TIMEOUT), True),
        (_outcome(success=False, error_type=CheckErrorType.CONNECTION), True),
        (_outcome(success=False, error_type=CheckErrorType.DNS), True),
        (_outcome(success=False, error_type=CheckErrorType.SSL), False),
        (_outcome(success=False, error_type=CheckErrorType.INVALID_URL), False),
        (_outcome(success=False, error_type=CheckErrorType.STATUS_CODE, status_code=404), False),
        (_outcome(success=False, error_type=CheckErrorType.STATUS_CODE, status_code=500), True),
        (_outcome(success=False, error_type=CheckErrorType.STATUS_CODE, status_code=503), True),
    ],
)
def test_is_retryable(outcome: CheckOutcome, expected: bool) -> None:
    assert is_retryable(outcome) is expected


def test_backoff_grows_exponentially() -> None:
    with patch("app.monitoring.retry.random.uniform", return_value=0):
        assert calculate_backoff_seconds(1, base_delay_seconds=1.0, max_delay_seconds=30.0) == 1.0
        assert calculate_backoff_seconds(2, base_delay_seconds=1.0, max_delay_seconds=30.0) == 2.0
        assert calculate_backoff_seconds(3, base_delay_seconds=1.0, max_delay_seconds=30.0) == 4.0


def test_backoff_respects_max_delay() -> None:
    with patch("app.monitoring.retry.random.uniform", return_value=0):
        delay = calculate_backoff_seconds(10, base_delay_seconds=1.0, max_delay_seconds=5.0)
        assert delay == 5.0


def test_backoff_includes_jitter() -> None:
    with patch("app.monitoring.retry.random.uniform", return_value=0.5):
        delay = calculate_backoff_seconds(1, base_delay_seconds=2.0, max_delay_seconds=30.0)
        assert delay == 2.5
