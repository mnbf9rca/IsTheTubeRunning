"""Tests for Celery database utilities.

These tests verify the session creation functions work correctly.
They use the worker's event loop to avoid conflicts with pytest-asyncio.
"""

from app.celery.database import (
    get_worker_loop,
    get_worker_session,
    get_worker_session_context,
    init_worker_resources,
)
from sqlalchemy.ext.asyncio import AsyncSession


def test_get_worker_session_context_is_async_generator() -> None:
    """Test get_worker_session_context returns an async generator."""
    # Ensure worker is initialized
    init_worker_resources()

    # Verify it's an async generator
    result = get_worker_session_context()
    assert hasattr(result, "__anext__")
    assert hasattr(result, "__aiter__")


def test_get_worker_session_returns_async_session() -> None:
    """Test get_worker_session returns an AsyncSession instance."""
    # Ensure worker is initialized
    init_worker_resources()

    session = get_worker_session()
    try:
        assert session is not None
        assert isinstance(session, AsyncSession)
    finally:
        # Close synchronously since we're not in async context
        loop = get_worker_loop()
        loop.run_until_complete(session.close())
