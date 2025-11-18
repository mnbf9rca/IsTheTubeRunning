"""Integration tests for Celery database connection handling.

Tests the worker_process_init signal handler and lazy engine initialization
that prevent asyncpg event loop conflicts in forked worker processes.

See Issue #147, #190, #195 and ADR 08 "Worker Pool Fork Safety" for context.
"""

import asyncio
import inspect

import pytest
from app.celery.database import (
    RedisClientProtocol,
    _get_worker_engine,
    cleanup_worker_resources,
    get_worker_redis_client,
    get_worker_session,
    init_worker_resources,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def test_init_worker_resources_exists_and_callable() -> None:
    """
    Test that init_worker_resources function exists and can be called.

    This verifies the signal handler is properly defined and executes without errors.
    """
    assert callable(init_worker_resources)
    # Should run without error in test environment
    init_worker_resources()


def test_init_worker_resources_accepts_kwargs() -> None:
    """
    Test that init_worker_resources accepts **kwargs.

    Celery signals pass arbitrary keyword arguments, so the handler
    must accept **kwargs even if it doesn't use them.
    """
    # Call with various kwargs (simulating Celery signal behavior)
    try:
        init_worker_resources(sender="test", signal="test_signal", extra="data")
    except TypeError:
        pytest.fail("init_worker_resources should accept **kwargs")


def test_init_worker_resources_creates_event_loop() -> None:
    """
    Test that init_worker_resources creates a persistent event loop.

    The signal handler creates a persistent event loop that will be used
    for all tasks in the worker process.
    """
    # Call the initialization
    init_worker_resources()

    # Verify an event loop exists and is accessible
    loop = asyncio.get_event_loop()
    assert loop is not None
    assert loop.is_running() is False  # Not running yet, just set


def test_cleanup_worker_resources_exists_and_callable() -> None:
    """
    Test that cleanup_worker_resources function exists and can be called.

    This verifies the shutdown signal handler is properly defined.
    """
    assert callable(cleanup_worker_resources)
    # Note: We don't call it here as it would close the event loop


def test_cleanup_worker_resources_accepts_kwargs() -> None:
    """
    Test that cleanup_worker_resources accepts **kwargs.

    Celery signals pass arbitrary keyword arguments, so the handler
    must accept **kwargs even if it doesn't use them.
    """
    # First initialize to set up resources
    init_worker_resources()

    # Call cleanup with various kwargs (simulating Celery signal behavior)
    # This should not raise TypeError
    try:
        cleanup_worker_resources(sender="test", signal="test_signal", extra="data")
    except TypeError:
        pytest.fail("cleanup_worker_resources should accept **kwargs")

    # Re-initialize for subsequent tests
    init_worker_resources()


@pytest.mark.asyncio
async def test_get_worker_session_creates_session() -> None:
    """
    Test that get_worker_session creates working session.

    This verifies that the session function can create functional sessions
    with connection pooling enabled in all environments.
    """
    # Create a session using get_worker_session
    session = get_worker_session()
    try:
        # Basic test - verify we can create and close session
        assert session is not None
        # Verify session is an AsyncSession
        assert isinstance(session, AsyncSession)
    finally:
        # Clean up
        await session.close()


@pytest.mark.asyncio
async def test_lazy_engine_initialization() -> None:
    """
    Test that engine is created lazily on first access.

    This verifies the lazy initialization pattern:
    1. Engine is None initially (per process)
    2. First access creates the engine
    3. Subsequent accesses reuse the same engine
    """
    # Get the engine (will create if needed)
    engine1 = _get_worker_engine()
    assert engine1 is not None

    # Get it again - should be the same instance
    engine2 = _get_worker_engine()
    assert engine1 is engine2

    # Verify we can create a session and execute a query
    session = get_worker_session()
    try:
        result = await session.execute(text("SELECT 1"))
        row = result.scalar()
        assert row == 1
    finally:
        await session.close()


def test_get_worker_redis_client_returns_client() -> None:
    """
    Test that get_worker_redis_client returns a Redis client.

    The client is created lazily on first access and satisfies
    the RedisClientProtocol interface.
    """
    # Get the Redis client
    client = get_worker_redis_client()
    assert client is not None

    # Verify it satisfies the protocol interface
    assert hasattr(client, "get")
    assert hasattr(client, "setex")
    assert hasattr(client, "aclose")


def test_get_worker_redis_client_returns_same_instance() -> None:
    """
    Test that get_worker_redis_client returns the same instance on repeated calls.

    The Redis client is shared across all tasks in the same worker process.
    """
    # Get the client twice
    client1 = get_worker_redis_client()
    client2 = get_worker_redis_client()

    # Should be the same instance
    assert client1 is client2


def test_redis_client_protocol_exported() -> None:
    """
    Test that RedisClientProtocol is exported from the module.

    Other modules should be able to import and use this protocol
    for type hints.
    """
    assert RedisClientProtocol is not None
    # Verify it's a Protocol (has the right attributes)
    # We can't easily check if it's a Protocol class, but we can verify
    # the expected methods exist in the class definition
    members = [name for name, _ in inspect.getmembers(RedisClientProtocol)]
    assert "get" in members or hasattr(RedisClientProtocol, "get")
    assert "setex" in members or hasattr(RedisClientProtocol, "setex")
    assert "aclose" in members or hasattr(RedisClientProtocol, "aclose")
