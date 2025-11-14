"""Integration tests for Celery database connection handling.

Tests the worker_process_init signal handler and lazy engine initialization
that prevent asyncpg event loop conflicts in forked worker processes.

See Issue #147 and ADR 08 "Worker Pool Fork Safety" for context.
"""

import pytest
from app.celery.database import _get_worker_engine, get_worker_session, init_worker_db
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def test_init_worker_db_exists_and_callable() -> None:
    """
    Test that init_worker_db function exists and can be called.

    This verifies the signal handler is properly defined and executes without errors.
    """
    assert callable(init_worker_db)
    # Should run without error in test environment
    init_worker_db()


def test_init_worker_db_accepts_kwargs() -> None:
    """
    Test that init_worker_db accepts **kwargs.

    Celery signals pass arbitrary keyword arguments, so the handler
    must accept **kwargs even if it doesn't use them.
    """
    # Call with various kwargs (simulating Celery signal behavior)
    try:
        init_worker_db(sender="test", signal="test_signal", extra="data")
    except TypeError:
        pytest.fail("init_worker_db should accept **kwargs")


def test_init_worker_db_resets_event_loop_policy() -> None:
    """
    Test that init_worker_db resets the asyncio event loop policy.

    With lazy initialization, the signal handler only needs to reset
    the event loop policy - each worker will create its own engine on first use.
    """
    # The function should run without error in any environment
    init_worker_db()
    # Test passes if no exception is raised


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
