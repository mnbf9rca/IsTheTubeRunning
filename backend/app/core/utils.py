"""Core utility functions."""

from urllib.parse import urlparse, urlunparse


def convert_async_db_url_to_sync(database_url: str) -> str:
    """
    Convert an async database URL to a sync database URL.

    Converts postgresql+asyncpg:// to postgresql:// for use with
    synchronous database drivers like psycopg2.

    Args:
        database_url: The async database URL (e.g., postgresql+asyncpg://...)

    Returns:
        The sync database URL (e.g., postgresql://...)
    """
    parsed_url = urlparse(database_url)
    if "+asyncpg" in parsed_url.scheme:
        sync_scheme = parsed_url.scheme.replace("+asyncpg", "")
        return urlunparse(parsed_url._replace(scheme=sync_scheme))
    return database_url
