"""Unit tests for SSRF URL validation."""

import ipaddress
from unittest.mock import patch

import pytest

from app.core.exceptions import SSRFValidationError
from app.monitoring.ssrf import is_blocked_ip, validate_monitor_url


@pytest.mark.parametrize(
    ("ip", "blocked"),
    [
        ("127.0.0.1", True),
        ("10.0.0.1", True),
        ("192.168.1.1", True),
        ("169.254.169.254", True),
        ("0.0.0.1", True),
        ("93.184.216.34", False),
        ("8.8.8.8", False),
    ],
)
def test_is_blocked_ip(ip: str, blocked: bool) -> None:
    assert is_blocked_ip(ipaddress.ip_address(ip)) is blocked


@pytest.mark.asyncio
async def test_validate_monitor_url_blocks_localhost() -> None:
    with pytest.raises(SSRFValidationError, match="hostname"):
        await validate_monitor_url("http://localhost/health")


@pytest.mark.asyncio
async def test_validate_monitor_url_blocks_literal_private_ip() -> None:
    with pytest.raises(SSRFValidationError, match="blocked IP"):
        await validate_monitor_url("http://192.168.0.1/health")


@pytest.mark.asyncio
async def test_validate_monitor_url_blocks_metadata_ip() -> None:
    with pytest.raises(SSRFValidationError, match="blocked IP"):
        await validate_monitor_url("http://169.254.169.254/latest/meta-data/")


@pytest.mark.asyncio
async def test_validate_monitor_url_blocks_dns_rebinding() -> None:
    with patch(
        "app.monitoring.ssrf._resolve_host_ips",
        return_value=[ipaddress.ip_address("10.0.0.5")],
    ):
        with pytest.raises(SSRFValidationError, match="blocked IP"):
            await validate_monitor_url("https://example.com/health")


@pytest.mark.asyncio
async def test_validate_monitor_url_allows_public_host() -> None:
    with patch(
        "app.monitoring.ssrf._resolve_host_ips",
        return_value=[ipaddress.ip_address("93.184.216.34")],
    ):
        await validate_monitor_url("https://example.com/health")


@pytest.mark.asyncio
async def test_validate_monitor_url_rejects_non_http_scheme() -> None:
    with pytest.raises(SSRFValidationError, match="HTTP and HTTPS"):
        await validate_monitor_url("file:///etc/passwd")
