"""Database configuration and session management."""

import threading
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings

# Module-level globals for lazy initialization (fork-safety)
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None

# Thread locks for thread-safe singleton initialization
_engine_lock = threading.Lock()
_session_factory_lock = threading.Lock()


def get_engine() -> AsyncEngine:
    """
    Get or create database engine (lazy initialization).

    Lazy initialization prevents forked worker processes from inheriting
    the parent's engine with asyncio primitives bound to the parent's event loop.

    This is critical when deploying FastAPI with multiple uvicorn workers
    (--workers > 1) which use os.fork() to create worker processes.

    Thread-safe implementation using double-checked locking ensures only one
    engine instance is created even with concurrent access.

    Returns:
        AsyncEngine: SQLAlchemy async engine
    """
    global _engine  # noqa: PLW0603
    if _engine is None:
        with _engine_lock:
            if _engine is None:  # Double-checked locking
                if settings.DEBUG:
                    # Use NullPool in DEBUG mode to avoid event loop issues with pytest-asyncio
                    # NullPool doesn't accept pool_size/max_overflow parameters
                    _engine = create_async_engine(
                        settings.DATABASE_URL,
                        echo=settings.DATABASE_ECHO,
                        future=True,
                        poolclass=NullPool,
                    )
                else:
                    # Use connection pooling in production for better performance
                    _engine = create_async_engine(
                        settings.DATABASE_URL,
                        echo=settings.DATABASE_ECHO,
                        future=True,
                        pool_size=settings.DATABASE_POOL_SIZE,
                        max_overflow=settings.DATABASE_MAX_OVERFLOW,
                    )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """
    Get or create session factory (lazy initialization).

    Thread-safe implementation using double-checked locking ensures only one
    session factory instance is created even with concurrent access.

    Returns:
        async_sessionmaker[AsyncSession]: SQLAlchemy async session factory
    """
    global _session_factory  # noqa: PLW0603
    if _session_factory is None:
        with _session_factory_lock:
            if _session_factory is None:  # Double-checked locking
                _session_factory = async_sessionmaker(
                    get_engine(),
                    class_=AsyncSession,
                    expire_on_commit=False,
                    autocommit=False,
                    autoflush=False,
                )
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession]:
    """
    Dependency for getting async database sessions.

    Yields:
        AsyncSession: Database session
    """
    async with get_session_factory()() as session:
        try:
            yield session
        finally:
            await session.close()
