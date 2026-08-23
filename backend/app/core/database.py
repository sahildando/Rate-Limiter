"""Database URL normalization for production providers (e.g. Neon)."""

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_SSL_QUERY_KEYS = frozenset({"sslmode", "ssl"})


def normalize_async_database_url(database_url: str) -> str:
    """Convert standard PostgreSQL URLs to the asyncpg SQLAlchemy driver."""
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return database_url


def database_requires_ssl(database_url: str) -> bool:
    """Return True when the database connection should use TLS."""
    normalized = normalize_async_database_url(database_url).lower()
    if ".neon.tech" in normalized:
        return True

    parsed = urlparse(normalized)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    ssl_mode = query.get("sslmode", "").lower()
    ssl_flag = query.get("ssl", "").lower()
    return ssl_mode in {"require", "verify-ca", "verify-full"} or ssl_flag in {
        "require",
        "true",
        "1",
    }


def asyncpg_connect_args(database_url: str) -> dict[str, object]:
    """Build asyncpg connect_args for SQLAlchemy."""
    if database_requires_ssl(database_url):
        return {"ssl": True}
    return {}


def strip_unsupported_query_params(database_url: str) -> str:
    """Remove query params that asyncpg does not accept directly."""
    normalized = normalize_async_database_url(database_url)
    parsed = urlparse(normalized)
    if not parsed.query:
        return normalized

    filtered = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key not in _SSL_QUERY_KEYS
    ]
    return urlunparse(parsed._replace(query=urlencode(filtered)))
