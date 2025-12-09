"""
Shared Redis client protocol and factory for dependency injection.

This module provides a centralized Protocol definition and factory function
for creating Redis clients throughout the application, ensuring consistent
configuration and type safety.
"""

from typing import Protocol, cast

import redis.asyncio as redis

from app.core.config import settings


class RedisClientProtocol(Protocol):
    """
    Protocol for Redis async client used for dependency injection and testing.

    Defines the subset of redis.asyncio.Redis methods used in this application.
    This protocol allows for easy mocking in tests while maintaining type safety.
    """

    async def get(self, name: str) -> str | None:
        """Get the value at key name."""
        ...

    async def set(self, name: str, value: str) -> bool:
        """Set the value at key name (no expiration)."""
        ...

    async def setex(self, name: str, time: int, value: str) -> bool:
        """Set the value at key name with expiration time."""
        ...

    async def delete(self, *names: str) -> int:
        """Delete one or more keys."""
        ...

    async def ping(self) -> bool:
        """Ping the Redis server to check connectivity."""
        ...

    async def aclose(self, close_connection_pool: bool = True) -> None:
        """Close the client connection."""
        ...


async def get_redis_client() -> RedisClientProtocol:
    """
    Create Redis client with standard configuration.

    This factory function provides a single point for Redis client creation,
    centralizing configuration and type ignore annotations.

    Returns:
        Redis client instance that satisfies RedisClientProtocol

    Note:
        redis.from_url() is not yet fully typed in redis-py 5.2.1,
        so we use a single type ignore here rather than throughout the codebase.
    """
    return cast(
        RedisClientProtocol,
        redis.from_url(  # type: ignore[no-untyped-call]
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        ),
    )
