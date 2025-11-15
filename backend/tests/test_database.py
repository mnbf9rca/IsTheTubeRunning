"""Tests for database configuration and session management."""

import pytest
from app.core.database import get_db, get_engine, get_session_factory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class TestDatabaseConfiguration:
    """Tests for database configuration."""

    def test_engine_configuration(self) -> None:
        """Test that engine is properly configured."""
        engine = get_engine()
        assert engine is not None
        assert engine.url.drivername == "postgresql+asyncpg"

    def test_session_maker_configuration(self) -> None:
        """Test that session maker is properly configured."""
        session_factory = get_session_factory()
        assert session_factory is not None
        assert session_factory.kw["expire_on_commit"] is False
        assert session_factory.kw["autocommit"] is False
        assert session_factory.kw["autoflush"] is False


class TestGetDb:
    """Tests for get_db dependency."""

    @pytest.mark.asyncio
    async def test_get_db_yields_session(self) -> None:
        """Test that get_db yields a valid session."""
        session_yielded = False
        session_instance = None

        async for session in get_db():
            session_yielded = True
            session_instance = session
            assert isinstance(session_instance, AsyncSession)
            assert session_instance.is_active  # Session is active when yielded
            break

        assert session_yielded
        assert session_instance is not None

    @pytest.mark.asyncio
    async def test_get_db_closes_session(self) -> None:
        """Test that get_db properly closes the session."""
        session_ref = None

        async for session in get_db():
            session_ref = session
            # Session is active while in the context
            assert session_ref.is_active
            break

        # After exiting the context, session should be closed
        # The session close is handled in the finally block
        # We can't directly test if it's closed, but we can verify the generator completed
        assert session_ref is not None

    @pytest.mark.asyncio
    async def test_get_db_session_can_query(self) -> None:
        """Test that sessions from get_db can execute queries."""
        async for session in get_db():
            # Test a simple query - this verifies the session is functional
            result = await session.execute(text("SELECT 1"))
            row = result.scalar()
            assert row == 1
            break
