"""Database session management for Celery workers.

Workers need their own database engine and session factory separate from the
FastAPI application to avoid sharing connections across different processes.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool, QueuePool

from app.core.config import settings

# Create separate async engine for workers
# Use NullPool in test/debug environments to avoid connection pooling issues
# Use QueuePool in production for better performance with proper connection management
if settings.DEBUG:
    worker_engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DATABASE_ECHO,
        future=True,
        poolclass=NullPool,
    )
else:
    worker_engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DATABASE_ECHO,
        future=True,
        poolclass=QueuePool,
        pool_size=5,  # Maintain 5 connections per worker
        max_overflow=10,  # Allow up to 10 additional connections during peak load
        pool_pre_ping=True,  # Verify connection health before using
    )

# Create async session factory for workers
worker_session_factory = async_sessionmaker(
    worker_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_worker_session() -> AsyncGenerator[AsyncSession]:
    """
    Get a database session for worker tasks.

    This is a helper function for creating sessions in worker tasks.
    Properly handles session lifecycle with automatic cleanup.

    Yields:
        AsyncSession: Database session for worker task

    Example:
        async for session in get_worker_session():
            # Use session
            result = await session.execute(query)
            await session.commit()
    """
    async with worker_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
