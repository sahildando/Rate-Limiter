"""HTTP monitoring check engine."""

import socket
import ssl
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.exceptions import SSRFValidationError
from app.models.check import CheckErrorType
from app.models.monitor import HttpMethod, Monitor
from app.monitoring.client import get_http_client
from app.monitoring.ssrf import validate_monitor_url


@dataclass(frozen=True, slots=True)
class CheckOutcome:
    """Result of a single HTTP check attempt (before persistence)."""

    success: bool
    status_code: int | None
    response_time_ms: int | None
    error_type: CheckErrorType | None = None
    error_message: str | None = None
    attempt_number: int = 1


class HttpChecker:
    """Executes asynchronous HTTP checks against monitor targets."""

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        follow_redirects: bool = False,
    ) -> None:
        self._client = client
        self._follow_redirects = follow_redirects
        self._owns_client = client is None

    async def check(self, monitor: Monitor, *, attempt_number: int = 1) -> CheckOutcome:
        """Perform an HTTP check for the given monitor."""
        try:
            await validate_monitor_url(monitor.url)
        except SSRFValidationError as exc:
            return CheckOutcome(
                success=False,
                status_code=None,
                response_time_ms=0,
                error_type=CheckErrorType.INVALID_URL,
                error_message=exc.message,
                attempt_number=attempt_number,
            )

        client = self._client or await get_http_client()
        timeout = _build_timeout(monitor.timeout_ms)
        start = time.monotonic()

        try:
            response = await self._send_request(client, monitor, timeout)
            elapsed_ms = _elapsed_ms(start)
            success = response.status_code == monitor.expected_status_code

            if success:
                return CheckOutcome(
                    success=True,
                    status_code=response.status_code,
                    response_time_ms=elapsed_ms,
                    attempt_number=attempt_number,
                )

            return CheckOutcome(
                success=False,
                status_code=response.status_code,
                response_time_ms=elapsed_ms,
                error_type=CheckErrorType.STATUS_CODE,
                error_message=(
                    f"Expected status {monitor.expected_status_code}, "
                    f"got {response.status_code}"
                ),
                attempt_number=attempt_number,
            )
        except Exception as exc:
            error_type, error_message = classify_check_error(exc)
            return CheckOutcome(
                success=False,
                status_code=None,
                response_time_ms=_elapsed_ms(start),
                error_type=error_type,
                error_message=error_message,
                attempt_number=attempt_number,
            )

    async def _send_request(
        self,
        client: httpx.AsyncClient,
        monitor: Monitor,
        timeout: httpx.Timeout,
    ) -> httpx.Response:
        request_kwargs: dict[str, Any] = {
            "timeout": timeout,
            "follow_redirects": self._follow_redirects,
        }
        method = monitor.method.value if isinstance(monitor.method, HttpMethod) else monitor.method

        if method == HttpMethod.GET.value:
            return await client.get(monitor.url, **request_kwargs)
        if method == HttpMethod.HEAD.value:
            return await client.head(monitor.url, **request_kwargs)

        return await client.request(method, monitor.url, **request_kwargs)

    async def aclose(self) -> None:
        """Close the client if this checker instance owns it."""
        if self._owns_client and self._client is not None and not self._client.is_closed:
            await self._client.aclose()


def _build_timeout(timeout_ms: int) -> httpx.Timeout:
    """Convert monitor timeout (ms) to httpx.Timeout with all phases set."""
    seconds = timeout_ms / 1000.0
    return httpx.Timeout(connect=seconds, read=seconds, write=seconds, pool=seconds)


def _elapsed_ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


def classify_check_error(exc: Exception) -> tuple[CheckErrorType, str]:
    """Map an exception to a normalized error type and user-safe message."""
    if isinstance(exc, httpx.InvalidURL):
        return CheckErrorType.INVALID_URL, "Invalid URL"

    if isinstance(exc, httpx.TimeoutException):
        return CheckErrorType.TIMEOUT, "Request timed out"

    if isinstance(exc, httpx.ConnectError):
        if _is_ssl_error(exc):
            return CheckErrorType.SSL, "SSL certificate verification failed"
        if _is_dns_error(exc):
            return CheckErrorType.DNS, "DNS resolution failed"
        return CheckErrorType.CONNECTION, "Connection failed"

    if isinstance(exc, httpx.NetworkError):
        if _is_dns_error(exc):
            return CheckErrorType.DNS, "DNS resolution failed"
        return CheckErrorType.CONNECTION, "Network error"

    return CheckErrorType.UNKNOWN, "An unexpected error occurred"


def _is_dns_error(exc: BaseException) -> bool:
    current: BaseException | None = exc
    while current is not None:
        if isinstance(current, socket.gaierror):
            return True
        message = str(current).lower()
        if "name or service not known" in message or "nodename nor serv" in message:
            return True
        current = current.__cause__ or current.__context__
    return False


def _is_ssl_error(exc: BaseException) -> bool:
    current: BaseException | None = exc
    while current is not None:
        if isinstance(current, ssl.SSLError):
            return True
        message = str(current).lower()
        if "ssl" in message or "certificate" in message:
            return True
        current = current.__cause__ or current.__context__
    return False
