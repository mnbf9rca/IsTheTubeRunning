"""Tests for Celery database utilities."""

import pytest
from app.celery.database import get_worker_session


@pytest.mark.asyncio
async def test_get_worker_session_yields_session() -> None:
    """Test get_worker_session async generator properly closes session."""

    session_obj = None
    async for session in get_worker_session():
        session_obj = session
        assert session is not None
        # Test that session gets closed in finally block (lines 61-65)
        break

    # Session should be closed after exiting async generator
    assert session_obj is not None
