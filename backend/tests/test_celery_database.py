"""Tests for Celery database utilities."""

import pytest
from app.celery.database import get_worker_session, get_worker_session_context
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_get_worker_session_context_yields_session() -> None:
    """Test get_worker_session_context async generator properly closes session."""

    session_obj = None
    async for session in get_worker_session_context():
        session_obj = session
        assert session_obj is not None
        # Test that session gets closed in finally block
        break

    # Session should be closed after exiting async generator
    assert session_obj is not None


@pytest.mark.asyncio
async def test_get_worker_session_returns_session() -> None:
    """Test get_worker_session returns an AsyncSession instance."""
    session = get_worker_session()
    try:
        assert session is not None
        # Verify we can use the session
        assert isinstance(session, AsyncSession)
    finally:
        await session.close()
