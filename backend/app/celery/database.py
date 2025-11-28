"""Database session management for Celery workers.

Workers need their own database engine and session factory separate from the
FastAPI application to avoid sharing connections across different processes.

IMPORTANT: This module implements a persistent event loop per worker pattern.
The event loop is created when the worker process initializes (after fork) and
persists for the lifetime of the worker. All async tasks run in this loop,
allowing database connections and Redis clients to be properly pooled and reused.

See Issue #195, #190, #147 and ADR 08 "Worker Pool Fork Safety" for details.
"""

import asyncio
import contextlib
import threading
from collections.abc import AsyncGenerator
from typing import Protocol, cast

import redis.asyncio
import structlog
from celery.signals import worker_process_init, worker_process_shutdown
from opentelemetry import trace
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# Module-level globals for worker resources
# These are created once per worker process and reused across all tasks
_worker_loop: asyncio.AbstractEventLoop | None = None
_worker_engine: AsyncEngine | None = None
_worker_session_factory: async_sessionmaker[AsyncSession] | None = None
_worker_redis_client: "RedisClientProtocol | None" = None

# Track if worker SQLAlchemy has been instrumented for OTEL
_worker_sqlalchemy_instrumented: bool = False

# Lock for thread-safe lazy initialization (RLock for reentrant calls)
_init_lock = threading.RLock()

logger = structlog.get_logger(__name__)


class RedisClientProtocol(Protocol):
    """
    Protocol for Redis async client with proper type hints.

    redis-py 5.x provides aclose() but redis-stubs package doesn't include it,
    so we define this protocol to avoid type ignore comments everywhere.
    """

    async def get(self, name: str) -> str | None:
        """Get the value at key name."""
        ...

    async def set(self, name: str, value: str) -> bool:
        """Set the value at key name (no expiration)."""
        ...

    async def setex(self, name: str, time: int, value: str) -> bool:
        """Set the value at key name with expiration time."""
        ...

    async def aclose(self, close_connection_pool: bool = True) -> None:
        """Close the client connection."""
        ...


@worker_process_init.connect
def init_worker_resources(
    **kwargs: object,
) -> None:
    """
    Initialize persistent event loop and resources after worker process fork.

    This is called by Celery when a new worker process is created (after fork).
    It creates a persistent event loop that will be used for all tasks in this
    worker process. This allows database engine and Redis client to be reused
    across tasks with proper connection pooling.

    The event loop persists for the lifetime of the worker process. Resources
    (engine, Redis) are created lazily on first use, bound to this loop.
    """
    global _worker_loop  # noqa: PLW0603

    # Idempotent: if loop already exists and is open, reuse it
    if _worker_loop is not None and not _worker_loop.is_closed():
        logger.debug("worker_process_init_loop_already_exists")
        return

    logger.info("worker_process_init_creating_persistent_loop")

    # Create persistent event loop for this worker
    _worker_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_worker_loop)

    # Initialize OpenTelemetry for this worker (fork-safe: each worker gets its own providers)
    if settings.OTEL_ENABLED:
        from app.core.telemetry import (  # noqa: PLC0415  # Lazy import for fork-safety
            get_tracer_provider,
            set_logger_provider,
        )

        if provider := get_tracer_provider():
            trace.set_tracer_provider(provider)
            logger.info("worker_otel_tracer_provider_initialized")

        # Initialize LoggerProvider for log export
        set_logger_provider()
        logger.info("worker_otel_logger_provider_initialized")

    logger.info("worker_process_init_completed")


@worker_process_shutdown.connect
def cleanup_worker_resources(
    **kwargs: object,
) -> None:
    """
    Dispose resources and close event loop on worker shutdown.

    This is called by Celery when the worker process is shutting down.
    It properly disposes the database engine (closes all pooled connections)
    and Redis client, then closes the event loop.
    """
    global _worker_loop, _worker_engine, _worker_session_factory, _worker_redis_client, _worker_sqlalchemy_instrumented  # noqa: PLW0603
    logger.info("worker_process_shutdown_cleaning_up")

    if _worker_loop is not None:
        # Capture references and clear globals first to prevent race conditions
        # This ensures no new sessions/clients are created during disposal
        loop = _worker_loop
        engine = _worker_engine
        redis_client = _worker_redis_client

        # Clear globals immediately
        _worker_loop = None
        _worker_engine = None
        _worker_session_factory = None
        _worker_redis_client = None
        _worker_sqlalchemy_instrumented = False

        try:
            # Dispose database engine
            if engine is not None:
                logger.debug("disposing_worker_engine")
                loop.run_until_complete(engine.dispose())

            # Close Redis client
            if redis_client is not None:
                logger.debug("closing_worker_redis_client")
                loop.run_until_complete(redis_client.aclose())

            # Shutdown OpenTelemetry TracerProvider
            if settings.OTEL_ENABLED:
                from app.core.telemetry import shutdown_tracer_provider  # noqa: PLC0415  # Lazy import for fork-safety

                shutdown_tracer_provider()
                logger.debug("worker_otel_tracer_provider_shutdown")

        except Exception as exc:
            # Log but don't raise - we're shutting down
            logger.warning(
                "worker_shutdown_cleanup_error",
                error=str(exc),
                error_type=type(exc).__name__,
            )
        finally:
            # Cancel any pending tasks before closing the loop
            pending = asyncio.all_tasks(loop)
            if pending:
                logger.debug("cancelling_pending_tasks", count=len(pending))
                for task in pending:
                    task.cancel()
                # Give tasks a chance to handle cancellation
                with contextlib.suppress(Exception):
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

            # Close the event loop
            logger.debug("closing_worker_event_loop")
            loop.close()
            asyncio.set_event_loop(None)

    logger.info("worker_process_shutdown_completed")


def _get_worker_engine() -> AsyncEngine:
    """Get or create the worker database engine.

    Lazily creates the engine on first access. This ensures each forked
    worker process creates its own engine with fresh asyncio primitives
    bound to the worker's persistent event loop.

    Uses connection pooling (AsyncAdaptedQueuePool) in all environments.
    The pool is reused across all tasks in the same worker process.

    Thread-safe via double-checked locking pattern.
    """
    global _worker_engine, _worker_sqlalchemy_instrumented  # noqa: PLW0603
    if _worker_engine is None or (settings.OTEL_ENABLED and not _worker_sqlalchemy_instrumented):
        with _init_lock:
            # Double-check after acquiring lock
            if _worker_engine is None:
                _worker_engine = create_async_engine(
                    settings.DATABASE_URL,
                    echo=settings.DATABASE_ECHO,
                    pool_size=settings.DATABASE_POOL_SIZE,
                    max_overflow=settings.DATABASE_MAX_OVERFLOW,
                )
            # Instrument for OpenTelemetry tracing (inside lock for thread-safety)
            if settings.OTEL_ENABLED and not _worker_sqlalchemy_instrumented:
                from opentelemetry.instrumentation.sqlalchemy import (  # noqa: PLC0415
                    SQLAlchemyInstrumentor,  # Lazy import for fork-safety
                )

                SQLAlchemyInstrumentor().instrument(engine=_worker_engine.sync_engine)
                _worker_sqlalchemy_instrumented = True
                logger.debug("worker_sqlalchemy_instrumented")
    return _worker_engine


def get_worker_session() -> AsyncSession:
    """Get a worker database session.

    Creates the session factory on first access, using the lazily-created engine,
    then returns a new session instance.

    Note: Sessions should be closed after use. The underlying engine and
    connection pool persist across tasks for connection reuse.

    Thread-safe via double-checked locking pattern.

    Returns:
        AsyncSession: A new database session for the worker task
    """
    global _worker_session_factory  # noqa: PLW0603
    if _worker_session_factory is None:
        with _init_lock:
            # Double-check after acquiring lock
            if _worker_session_factory is None:
                _worker_session_factory = async_sessionmaker(
                    _get_worker_engine(),
                    class_=AsyncSession,
                    expire_on_commit=False,
                    autocommit=False,
                    autoflush=False,
                )
    return _worker_session_factory()


def get_worker_redis_client() -> "RedisClientProtocol":
    """Get the worker's shared Redis client.

    Creates the Redis client on first access. The client is reused across
    all tasks in the same worker process, bound to the worker's persistent
    event loop.

    Note: Do NOT call aclose() on this client in task code. The client
    lifecycle is managed by the worker shutdown signal handler.

    Thread-safe via double-checked locking pattern.

    Returns:
        RedisClientProtocol: Shared Redis client for this worker
    """
    global _worker_redis_client  # noqa: PLW0603
    if _worker_redis_client is None:
        with _init_lock:
            # Double-check after acquiring lock
            if _worker_redis_client is None:
                _worker_redis_client = cast(
                    RedisClientProtocol,
                    redis.asyncio.from_url(
                        settings.REDIS_URL,
                        encoding="utf-8",
                        decode_responses=True,
                    ),
                )
    return _worker_redis_client


def get_worker_loop() -> asyncio.AbstractEventLoop:
    """Get the worker's persistent event loop.

    This returns the event loop created during worker initialization.
    Raises RuntimeError if the worker has not been initialized or
    the loop has been closed.

    Returns:
        asyncio.AbstractEventLoop: The worker's event loop

    Raises:
        RuntimeError: If init_worker_resources was not called or loop is closed
    """
    if _worker_loop is None:
        msg = (
            "Worker event loop not initialized. "
            "Ensure init_worker_resources was called (via worker_process_init signal)."
        )
        raise RuntimeError(msg)
    if _worker_loop.is_closed():
        msg = "Worker event loop has been closed. Cannot run tasks after cleanup_worker_resources has been called."
        raise RuntimeError(msg)
    return _worker_loop


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
