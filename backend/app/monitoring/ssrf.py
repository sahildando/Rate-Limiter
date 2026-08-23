"""SSRF protection for user-supplied monitor URLs."""

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

from app.core.exceptions import SSRFValidationError

# AWS/GCP/Azure metadata endpoint.
_METADATA_IPV4 = ipaddress.ip_address("169.254.169.254")

_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "metadata.google.internal",
        "metadata.goog",
    }
)


def is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return True when an IP must not be contacted by the monitoring engine."""
    if ip == _METADATA_IPV4:
        return True

    if isinstance(ip, ipaddress.IPv4Address) and ip in ipaddress.ip_network("0.0.0.0/8"):
        return True

    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _validate_hostname(hostname: str) -> None:
    lowered = hostname.lower().rstrip(".")
    if lowered in _BLOCKED_HOSTNAMES:
        raise SSRFValidationError(
            "URL hostname is not allowed",
            code="SSRF_BLOCKED",
        )

    try:
        ip = ipaddress.ip_address(lowered)
    except ValueError:
        return

    if is_blocked_ip(ip):
        raise SSRFValidationError(
            "URL resolves to a blocked IP address",
            code="SSRF_BLOCKED",
        )


async def _resolve_host_ips(
    hostname: str,
    port: int,
) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Resolve hostname to IP addresses (DNS rebinding protection)."""
    loop = asyncio.get_running_loop()
    try:
        addr_info = await loop.getaddrinfo(
            hostname,
            port,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise SSRFValidationError(
            "URL hostname could not be resolved",
            code="SSRF_BLOCKED",
        ) from exc

    ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for _, _, _, _, sockaddr in addr_info:
        ips.append(ipaddress.ip_address(sockaddr[0]))
    return ips


async def validate_monitor_url(url: str) -> None:
    """
    Validate a monitor URL is safe to fetch.

    Checks scheme, hostname, literal IPs, and all resolved addresses.
    """
    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        raise SSRFValidationError(
            "Only HTTP and HTTPS URLs are allowed",
            code="SSRF_BLOCKED",
        )

    hostname = parsed.hostname
    if not hostname:
        raise SSRFValidationError("URL must include a hostname", code="SSRF_BLOCKED")

    _validate_hostname(hostname)

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    for ip in await _resolve_host_ips(hostname, port):
        if is_blocked_ip(ip):
            raise SSRFValidationError(
                "URL resolves to a blocked IP address",
                code="SSRF_BLOCKED",
            )
