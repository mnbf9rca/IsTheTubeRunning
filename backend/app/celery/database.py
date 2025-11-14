"""Database session management for Celery workers.

Workers need their own database engine and session factory separate from the
FastAPI application to avoid sharing connections across different processes.

IMPORTANT: When using Celery's ForkPoolWorker (default), the database engine
must be disposed after forking to avoid asyncpg errors. The worker_process_init
signal handler below ensures each forked worker creates fresh connections
instead of inheriting the parent's pooled connections.

See Issue #147 and ADR 08 "Worker Pool Fork Safety" for details.
"""

import asyncio
from collections.abc import AsyncGenerator

import structlog
from celery.signals import worker_process_init
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# Worker engine - created lazily per task to avoid event loop conflicts
# When using fork pool, creating the engine at import time causes asyncio.Queue
# objects inside the connection pool to be bound to the parent's event loop.
# Additionally, since each task gets a fresh event loop via run_in_isolated_loop(),
# the engine must be recreated for each task to bind asyncio primitives to the
# correct event loop.
_worker_engine: AsyncEngine | None = None
_worker_session_factory: async_sessionmaker[AsyncSession] | None = None


async def reset_worker_engine() -> None:
    """
    Reset worker engine globals to force fresh creation on next access.

    This must be called at the start of each task to ensure the engine's
    asyncio primitives are bound to the current task's event loop.

    Disposes the old engine before resetting to avoid connection leaks.
    """
    global _worker_engine, _worker_session_factory  # noqa: PLW0603
    if _worker_engine is not None:
        await _worker_engine.dispose()
    _worker_engine = None
    _worker_session_factory = None


def _get_worker_engine() -> AsyncEngine:
    """Get or create the worker database engine.

    Lazily creates the engine on first access. This ensures each forked
    worker process creates its own engine with fresh asyncio primitives,
    avoiding "Future attached to a different loop" errors.

    Uses connection pooling (AsyncAdaptedQueuePool) in all environments for
    consistency. The lazy initialization pattern ensures each worker process
    gets its own pool with asyncio primitives bound to the correct event loop.
    """
    global _worker_engine  # noqa: PLW0603
    if _worker_engine is None:
        _worker_engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DATABASE_ECHO,
            future=True,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
        )
    return _worker_engine


def get_worker_session() -> AsyncSession:
    """Get a worker database session.

    Creates the session factory on first access, using the lazily-created engine,
    then returns a new session instance.

    Returns:
        AsyncSession: A new database session for the worker task
    """
    global _worker_session_factory  # noqa: PLW0603
    if _worker_session_factory is None:
        _worker_session_factory = async_sessionmaker(
            _get_worker_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _worker_session_factory()


@worker_process_init.connect
def init_worker_db(**kwargs: object) -> None:
    """
    Reset asyncio state after worker process fork.

    Celery's ForkPoolWorker (default) creates child processes by forking the
    parent process. This function ensures each forked worker starts with a
    clean asyncio state by resetting the event loop policy.

    Note: With lazy engine initialization, we don't need to dispose anything
    at fork time - each worker will create its own fresh engine on first use.

    Args:
        **kwargs: Signal arguments (unused, required by Celery signal signature)
    """
    logger = structlog.get_logger(__name__)
    logger.info("worker_process_forked_resetting_event_loop")

    # Reset asyncio event loop policy to clear any inherited event loop state
    # This ensures fresh event loops in each worker process
    asyncio.set_event_loop_policy(None)


async def get_worker_session_context() -> AsyncGenerator[AsyncSession]:
    """
    Get a database session for worker tasks with context manager support.

    This is a helper function for creating sessions in worker tasks.
    Properly handles session lifecycle with automatic cleanup via async context manager.

    Yields:
        AsyncSession: Database session for worker task

    Example:
        async for session in get_worker_session_context():
            # Use session
            result = await session.execute(query)
            await session.commit()
    """
    async with get_worker_session() as session:
        yield session
