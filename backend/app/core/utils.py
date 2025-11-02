"""Core utility functions."""

from urllib.parse import urlparse, urlunparse


def convert_async_db_url_to_sync(database_url: str) -> str:
    """
    Convert an async database URL to a sync database URL.

    Converts postgresql+asyncpg:// to postgresql+psycopg:// for use with
    synchronous database drivers (psycopg3).

    Args:
        database_url: The async database URL (e.g., postgresql+asyncpg://...)

    Returns:
        The sync database URL (e.g., postgresql+psycopg://...)
    """
    parsed_url = urlparse(database_url)
    if "+asyncpg" in parsed_url.scheme:
        # Replace asyncpg with psycopg (psycopg3)
        sync_scheme = parsed_url.scheme.replace("+asyncpg", "+psycopg")
        return urlunparse(parsed_url._replace(scheme=sync_scheme))
    return database_url
