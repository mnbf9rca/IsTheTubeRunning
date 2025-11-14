# Celery Fork Safety Implementation

This document describes the implementation details for Issue #147 - Celery worker database connection errors with asyncpg.

## Problem

SQLAlchemy's async engine creates `asyncio.Queue` objects at construction time that become permanently bound to the event loop that created them. This causes conflicts in two scenarios:

1. **Cross-process binding:** Engine created at import time → forked workers inherit Queue objects bound to parent's event loop
2. **Cross-task binding:** Engine created lazily but persists across tasks → each task gets fresh event loop but reuses engine with Queue objects bound to first task's event loop

Both cause:
```
RuntimeError: Task <Task> got Future <Future> attached to a different loop
asyncpg.exceptions._base.InterfaceError: cannot perform operation: another operation is in progress
```

## Solution

Combine three techniques:

1. **Lazy engine initialization** - Defer creation until first access
2. **Per-task engine reset** - Reset globals at start of each task
3. **Event loop policy reset** - Clear inherited state after fork

## Implementation

### 1. database.py - Lazy Initialization

```python
import asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

# Module-level globals for lazy initialization
_worker_engine: AsyncEngine | None = None
_worker_session_factory: async_sessionmaker[AsyncSession] | None = None

async def reset_worker_engine() -> None:
    """Reset engine globals to force fresh creation on next access.

    Disposes the old engine before resetting to avoid connection leaks.
    """
    global _worker_engine, _worker_session_factory  # noqa: PLW0603
    if _worker_engine is not None:
        await _worker_engine.dispose()
    _worker_engine = None
    _worker_session_factory = None

def _get_worker_engine() -> AsyncEngine:
    """Get or create worker engine (lazy initialization)."""
    global _worker_engine  # noqa: PLW0603
    if _worker_engine is None:
        _worker_engine = create_async_engine(
            settings.DATABASE_URL,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
            echo=settings.DATABASE_ECHO,
            future=True,
        )
    return _worker_engine

def get_worker_session() -> AsyncSession:
    """Get a worker database session."""
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
    """Reset asyncio event loop policy after fork."""
    asyncio.set_event_loop_policy(None)
```

### 2. tasks.py - Per-Task Reset

Add `await reset_worker_engine()` call at the start of each async task function:

```python
from app.celery.database import get_worker_session, reset_worker_engine

async def _check_disruptions_async() -> DisruptionCheckResult:
    # Force fresh engine for this task's event loop
    await reset_worker_engine()

    session = None
    redis_client = None
    try:
        session = get_worker_session()
        redis_client = await get_redis_client()
        # ... rest of task logic
```

Apply the same pattern to all async task functions:
- `_check_disruptions_async()`
- `_rebuild_indexes_async()`
- `_detect_stale_routes_async()`

### 3. tasks.py - Event Loop Helper

The `run_in_isolated_loop()` helper creates a fresh, isolated event loop for each task:

```python
def run_in_isolated_loop(coro_func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Run an async function in a fresh, isolated event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        coro = coro_func(*args, **kwargs)
        return loop.run_until_complete(coro)
    finally:
        # Cancel any pending tasks
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()
        asyncio.set_event_loop(None)
```

## Key Insight

Since each task gets a fresh event loop via `run_in_isolated_loop()`, the engine's asyncio primitives must be recreated for each task to bind to the correct loop. This is achieved by resetting the engine globals, forcing lazy re-initialization per task.

## Testing

Updated test mocks from `@patch("app.celery.tasks.asyncio.run")` to `@patch("app.celery.tasks.run_in_isolated_loop")` since we now use the custom helper.

## Trade-offs

**Pros:**
- Complete event loop isolation between tasks and workers
- Connection pooling works in all environments (no DEBUG conditional)
- No asyncpg errors or event loop conflicts

**Cons:**
- Engine is recreated per task (small overhead, but necessary for correctness)
- Connection pool is not shared across tasks in the same worker process
- Must remember to call `await reset_worker_engine()` at start of new async tasks

## Files Changed

- `backend/app/celery/database.py` - Lazy initialization with per-task reset
- `backend/app/celery/tasks.py` - Added `await reset_worker_engine()` calls to all async task functions
- `backend/tests/test_celery_tasks.py` - Updated mocks to patch `run_in_isolated_loop`
- `backend/tests/test_celery_database_integration.py` - Added/updated integration tests
- `docs/adr/08-background-jobs.md` - Documented decision

## References

- Issue #147: https://github.com/mnbf9rca/IsTheTubeRunning/issues/147
- SQLAlchemy docs: [Using Connection Pools with Multiprocessing](https://docs.sqlalchemy.org/en/20/core/pooling.html#using-connection-pools-with-multiprocessing-or-os-fork)
- Celery signals: [worker_process_init](https://docs.celeryq.dev/en/stable/userguide/signals.html#worker-process-init)
