"""Database session management for Celery workers.

Workers need their own database engine and session factory separate from the
FastAPI application to avoid sharing connections across different processes.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

# Create separate async engine for workers (separate from FastAPI app engine)
# Use NullPool in tests to avoid event loop issues with pytest-asyncio
# Use default async pool (AsyncAdaptedQueuePool) in production for performance
worker_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DATABASE_ECHO,
    future=True,
    poolclass=NullPool if settings.DEBUG else None,
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
