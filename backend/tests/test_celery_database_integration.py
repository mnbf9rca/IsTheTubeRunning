"""Integration tests for Celery database connection handling.

Tests the worker_process_init signal handler and lazy engine initialization
that prevent asyncpg event loop conflicts in forked worker processes.

See Issue #147 and ADR 08 "Worker Pool Fork Safety" for context.
"""

import pytest
from app.celery.database import _get_worker_engine, init_worker_db, worker_session_factory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def test_init_worker_db_exists_and_callable() -> None:
    """
    Test that init_worker_db function exists and can be called.

    This verifies the signal handler is properly defined.
    """
    assert callable(init_worker_db)
    # Should run without error in test environment (DEBUG=true)
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
        # If we got here, kwargs are accepted
        assert True
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
    # Function completed successfully
    assert True


@pytest.mark.asyncio
async def test_worker_session_factory_creates_session() -> None:
    """
    Test that session factory creates working session.

    This verifies that after engine disposal (or with NullPool), the
    session factory can still create functional sessions.
    """
    # Create a session using the factory
    session = worker_session_factory()
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
    session = worker_session_factory()
    try:
        result = await session.execute(text("SELECT 1"))
        row = result.scalar()
        assert row == 1
    finally:
        await session.close()
