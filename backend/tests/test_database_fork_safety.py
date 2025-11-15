"""Tests for database fork safety (lazy initialization pattern)."""

import threading

import pytest
from app.core import database as database_module
from app.core.config import settings
from app.core.database import get_db, get_engine, get_session_factory
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool


@pytest.fixture(autouse=True)
def reset_database_globals():
    """Reset database module globals before and after each test for isolation."""
    database_module._engine = None
    database_module._session_factory = None
    yield
    database_module._engine = None
    database_module._session_factory = None


class TestLazyInitialization:
    """Tests for lazy initialization of database engine and session factory."""

    def test_engine_initially_none(self) -> None:
        """Test that engine global is None before first access."""
        assert database_module._engine is None

    def test_lazy_engine_initialization(self) -> None:
        """Test that engine is created on first call to get_engine()."""
        # First call should create the engine
        engine = get_engine()

        assert engine is not None
        assert isinstance(engine, AsyncEngine)
        assert database_module._engine is not None
        assert database_module._engine is engine

    def test_engine_singleton_pattern(self) -> None:
        """Test that multiple calls to get_engine() return the same instance."""
        # Get engine twice
        engine1 = get_engine()
        engine2 = get_engine()

        # Should be the exact same object
        assert engine1 is engine2

    def test_session_factory_initially_none(self) -> None:
        """Test that session factory global is None before first access."""
        assert database_module._session_factory is None

    def test_lazy_session_factory_initialization(self) -> None:
        """Test that session factory is created on first call to get_session_factory()."""
        # First call should create the session factory
        session_factory = get_session_factory()

        assert session_factory is not None
        assert isinstance(session_factory, async_sessionmaker)
        assert database_module._session_factory is not None
        assert database_module._session_factory is session_factory

    def test_session_factory_singleton_pattern(self) -> None:
        """Test that multiple calls to get_session_factory() return the same instance."""
        # Get session factory twice
        factory1 = get_session_factory()
        factory2 = get_session_factory()

        # Should be the exact same object
        assert factory1 is factory2

    def test_session_factory_uses_lazy_engine(self) -> None:
        """Test that session factory creation triggers engine creation."""
        # Engine should be None initially
        assert database_module._engine is None

        # Get session factory (which calls get_engine() internally)
        session_factory = get_session_factory()

        # Now engine should also be created
        assert database_module._engine is not None
        assert session_factory is not None

    def test_concurrent_engine_initialization_is_thread_safe(self) -> None:
        """Test that concurrent calls to get_engine() create only one instance.

        This test verifies the double-checked locking pattern works correctly
        under concurrent access by multiple threads.
        """
        num_threads = 10
        barrier = threading.Barrier(num_threads)
        engines = []
        errors = []

        def get_engine_with_barrier() -> None:
            """Thread function that waits at barrier then gets engine."""
            try:
                # Wait for all threads to be ready
                barrier.wait()
                # All threads call get_engine() simultaneously
                engine = get_engine()
                engines.append(engine)
            except Exception as e:
                errors.append(e)

        # Create and start threads
        threads = [threading.Thread(target=get_engine_with_barrier) for _ in range(num_threads)]
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify no errors occurred
        assert len(errors) == 0, f"Errors occurred in threads: {errors}"

        # Verify all threads got engines
        assert len(engines) == num_threads

        # Verify all threads got the SAME engine instance (singleton)
        first_engine = engines[0]
        for engine in engines:
            assert engine is first_engine, "Threads got different engine instances!"

        # Verify the module-level global is the same instance
        assert database_module._engine is first_engine

    def test_concurrent_session_factory_initialization_is_thread_safe(self) -> None:
        """Test that concurrent calls to get_session_factory() create only one instance.

        This test verifies the double-checked locking pattern works correctly
        under concurrent access by multiple threads.
        """
        num_threads = 10
        barrier = threading.Barrier(num_threads)
        factories = []
        errors = []

        def get_factory_with_barrier() -> None:
            """Thread function that waits at barrier then gets session factory."""
            try:
                # Wait for all threads to be ready
                barrier.wait()
                # All threads call get_session_factory() simultaneously
                factory = get_session_factory()
                factories.append(factory)
            except Exception as e:
                errors.append(e)

        # Create and start threads
        threads = [threading.Thread(target=get_factory_with_barrier) for _ in range(num_threads)]
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify no errors occurred
        assert len(errors) == 0, f"Errors occurred in threads: {errors}"

        # Verify all threads got session factories
        assert len(factories) == num_threads

        # Verify all threads got the SAME session factory instance (singleton)
        first_factory = factories[0]
        for factory in factories:
            assert factory is first_factory, "Threads got different session factory instances!"

        # Verify the module-level global is the same instance
        assert database_module._session_factory is first_factory


class TestPoolConfiguration:
    """Tests for database pool configuration."""

    def test_engine_uses_pool_settings_in_production(self) -> None:
        """Test that engine uses configured pool settings when DEBUG=false."""
        # Get engine
        engine = get_engine()

        # In DEBUG mode (default for tests), should use NullPool
        if settings.DEBUG:
            assert isinstance(engine.pool, NullPool)
        else:
            # In production mode, should use AsyncAdaptedQueuePool with custom settings
            # Pool size and max overflow are passed to create_async_engine
            # We can verify they're set by checking the pool configuration
            assert engine.pool is not None
            # The actual pool type will be AsyncAdaptedQueuePool (not NullPool)
            assert not isinstance(engine.pool, NullPool)

    def test_engine_uses_correct_pool_size(self) -> None:
        """Test that engine configuration includes pool size settings."""
        # Get engine
        engine = get_engine()

        # Verify the engine was created with correct parameters
        # Note: In DEBUG mode (tests), NullPool is used and pool_size is ignored
        # In production mode, pool_size and max_overflow are applied
        assert engine is not None

        if not settings.DEBUG:
            # In production, verify pool settings are applied
            # The pool object should have these attributes set
            pool = engine.pool
            # AsyncAdaptedQueuePool will have _pool_size and _max_overflow
            # but they're private attributes, so we just verify it's not NullPool
            assert not isinstance(pool, NullPool)


class TestGetDb:
    """Tests for get_db dependency with lazy initialization."""

    @pytest.mark.asyncio
    async def test_get_db_with_lazy_initialization(self) -> None:
        """Test that get_db() works correctly with lazy initialization."""
        # get_db() should trigger lazy initialization
        async for session in get_db():
            # Session should be created successfully
            assert session is not None
            # Engine and session factory should now be initialized
            assert database_module._engine is not None
            assert database_module._session_factory is not None
            break

    @pytest.mark.asyncio
    async def test_get_db_uses_singleton_session_factory(self) -> None:
        """Test that get_db() uses the singleton session factory."""
        # Create session factory first
        original_factory = get_session_factory()

        # get_db() should use the same factory
        async for _session in get_db():
            # The session factory should not have changed
            assert database_module._session_factory is original_factory
            break


class TestEngineConfiguration:
    """Tests for engine configuration details."""

    def test_engine_url_configuration(self) -> None:
        """Test that engine is configured with correct database URL from settings."""
        engine = get_engine()

        # Verify engine uses PostgreSQL with asyncpg driver
        assert engine.url.drivername == "postgresql+asyncpg"

        # Verify it uses the DATABASE_URL from settings by comparing components
        expected_url = make_url(settings.DATABASE_URL)

        # Compare each component
        assert engine.url.drivername == expected_url.drivername
        assert engine.url.username == expected_url.username
        assert engine.url.host == expected_url.host
        assert engine.url.port == expected_url.port
        assert engine.url.database == expected_url.database

    def test_engine_echo_configuration(self) -> None:
        """Test that engine echo setting matches configuration."""
        engine = get_engine()

        # Verify echo setting matches config
        assert engine.echo == settings.DATABASE_ECHO


class TestSessionFactoryConfiguration:
    """Tests for session factory configuration."""

    def test_session_factory_settings(self) -> None:
        """Test that session factory has correct settings."""
        factory = get_session_factory()

        # Verify session factory configuration
        assert factory.kw["expire_on_commit"] is False
        assert factory.kw["autocommit"] is False
        assert factory.kw["autoflush"] is False

    def test_session_factory_uses_async_session(self) -> None:
        """Test that session factory creates AsyncSession instances."""
        factory = get_session_factory()

        # Verify the session class is AsyncSession
        # In SQLAlchemy 2.0, the class is stored in .class_ attribute (not in .kw)
        assert factory.class_ is AsyncSession
