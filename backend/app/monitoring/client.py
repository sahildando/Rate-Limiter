"""Shared httpx AsyncClient with connection pooling."""

import httpx

_client: httpx.AsyncClient | None = None


async def get_http_client() -> httpx.AsyncClient:
    """Return a reusable async HTTP client with connection pooling."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            follow_redirects=False,
        )
    return _client


async def close_http_client() -> None:
    """Close the shared HTTP client (called on application shutdown)."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
