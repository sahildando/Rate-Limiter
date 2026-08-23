"""Unit tests for the HTTP check engine."""

import socket
import ssl
import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.models.check import CheckErrorType
from app.models.monitor import HttpMethod, Monitor, MonitorStatus
from app.monitoring.checker import HttpChecker, classify_check_error


@pytest.fixture(autouse=True)
def mock_ssrf_validation() -> AsyncMock:
    with patch(
        "app.monitoring.checker.validate_monitor_url",
        new=AsyncMock(return_value=None),
    ) as mocked:
        yield mocked


def _make_monitor(*, expected_status_code: int = 200, timeout_ms: int = 5000) -> Monitor:
    return Monitor(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Test Monitor",
        url="https://example.com/health",
        method=HttpMethod.GET,
        expected_status_code=expected_status_code,
        interval_seconds=60,
        timeout_ms=timeout_ms,
        enabled=True,
        status=MonitorStatus.PENDING,
        failure_count=0,
        consecutive_failure_count=0,
    )


def _checker_with_handler(handler: httpx.MockTransport) -> HttpChecker:
    client = httpx.AsyncClient(transport=handler)
    return HttpChecker(client)


@pytest.mark.asyncio
async def test_check_success_200() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200)

    checker = _checker_with_handler(httpx.MockTransport(handler))
    outcome = await checker.check(_make_monitor())

    assert outcome.success is True
    assert outcome.status_code == 200
    assert outcome.response_time_ms is not None
    assert outcome.response_time_ms >= 0
    assert outcome.error_type is None
    await checker.aclose()


@pytest.mark.asyncio
async def test_check_failure_404() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    checker = _checker_with_handler(httpx.MockTransport(handler))
    outcome = await checker.check(_make_monitor())

    assert outcome.success is False
    assert outcome.status_code == 404
    assert outcome.error_type == CheckErrorType.STATUS_CODE
    assert outcome.error_message is not None
    await checker.aclose()


@pytest.mark.asyncio
async def test_check_failure_500() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    checker = _checker_with_handler(httpx.MockTransport(handler))
    outcome = await checker.check(_make_monitor())

    assert outcome.success is False
    assert outcome.status_code == 500
    assert outcome.error_type == CheckErrorType.STATUS_CODE
    await checker.aclose()


@pytest.mark.asyncio
async def test_check_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    checker = _checker_with_handler(httpx.MockTransport(handler))
    outcome = await checker.check(_make_monitor())

    assert outcome.success is False
    assert outcome.error_type == CheckErrorType.TIMEOUT
    assert outcome.error_message == "Request timed out"
    await checker.aclose()


@pytest.mark.asyncio
async def test_check_dns_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(
            "nodename nor servname provided",
            request=request,
        )

    checker = _checker_with_handler(httpx.MockTransport(handler))
    outcome = await checker.check(_make_monitor())

    assert outcome.success is False
    assert outcome.error_type == CheckErrorType.DNS
    await checker.aclose()


@pytest.mark.asyncio
async def test_check_ssl_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(
            "SSL certificate verify failed",
            request=request,
        )

    checker = _checker_with_handler(httpx.MockTransport(handler))
    outcome = await checker.check(_make_monitor())

    assert outcome.success is False
    assert outcome.error_type == CheckErrorType.SSL
    await checker.aclose()


@pytest.mark.asyncio
async def test_check_connection_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    checker = _checker_with_handler(httpx.MockTransport(handler))
    outcome = await checker.check(_make_monitor())

    assert outcome.success is False
    assert outcome.error_type == CheckErrorType.CONNECTION
    await checker.aclose()


@pytest.mark.asyncio
async def test_check_head_method() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "HEAD"
        return httpx.Response(200)

    checker = _checker_with_handler(httpx.MockTransport(handler))
    monitor = _make_monitor()
    monitor.method = HttpMethod.HEAD
    outcome = await checker.check(monitor)

    assert outcome.success is True
    await checker.aclose()


def test_classify_dns_error_from_gaierror() -> None:
    exc = httpx.ConnectError("failed")
    exc.__cause__ = socket.gaierror("Name or service not known")
    error_type, message = classify_check_error(exc)
    assert error_type == CheckErrorType.DNS


def test_classify_ssl_error_from_ssl_error() -> None:
    exc = httpx.ConnectError("failed")
    exc.__cause__ = ssl.SSLError("certificate verify failed")
    error_type, _ = classify_check_error(exc)
    assert error_type == CheckErrorType.SSL


def test_classify_invalid_url() -> None:
    error_type, message = classify_check_error(httpx.InvalidURL("bad url"))
    assert error_type == CheckErrorType.INVALID_URL
    assert message == "Invalid URL"
