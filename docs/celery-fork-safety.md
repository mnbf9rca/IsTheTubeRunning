# Celery Fork Safety Implementation

This document describes the implementation details for Issue #195 - Persistent event loop per Celery worker.

## Problem

SQLAlchemy's async engine creates `asyncio.Queue` objects at construction time that become permanently bound to the event loop that created them. This causes conflicts in forked Celery workers:

1. **Per-task loop issue:** Each task creates a fresh event loop via `run_in_isolated_loop()`, but the database engine from the previous task is bound to the old (now closed) loop
2. **Engine disposal failure:** When a new task tries to dispose the old engine, it fails because the engine's connections are bound to the closed loop

This causes:
```
RuntimeError: Event loop is closed
RuntimeError: Task <Task> got Future <Future> attached to a different loop
asyncpg.exceptions._base.InterfaceError: cannot perform operation: another operation is in progress
```

## Solution

Use a **persistent event loop per worker** that lives for the entire worker process lifetime:

1. **Persistent event loop** - Created at worker initialization, persists across all tasks
2. **Shared resources** - Database engine and Redis client are shared across tasks
3. **Proper cleanup** - Resources are disposed on worker shutdown

## Implementation

### 1. database.py - Persistent Loop with Lazy Resource Initialization

```python
import asyncio
from celery.signals import worker_process_init, worker_process_shutdown

# Module-level globals for worker resources
_worker_loop: asyncio.AbstractEventLoop | None = None
_worker_engine: AsyncEngine | None = None
_worker_session_factory: async_sessionmaker[AsyncSession] | None = None
_worker_redis_client: RedisClientProtocol | None = None

@worker_process_init.connect
def init_worker_resources(**kwargs: object) -> None:
    """Create persistent event loop after worker fork."""
    global _worker_loop

    # Create persistent event loop for this worker
    _worker_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_worker_loop)

@worker_process_shutdown.connect
def cleanup_worker_resources(**kwargs: object) -> None:
    """Dispose resources and close event loop on worker shutdown."""
    global _worker_loop, _worker_engine, _worker_redis_client

    if _worker_loop is not None:
        # Dispose database engine
        if _worker_engine is not None:
            _worker_loop.run_until_complete(_worker_engine.dispose())
            _worker_engine = None

        # Close Redis client
        if _worker_redis_client is not None:
            _worker_loop.run_until_complete(_worker_redis_client.aclose())
            _worker_redis_client = None

        # Close the event loop
        _worker_loop.close()
        _worker_loop = None

def _get_worker_engine() -> AsyncEngine:
    """Get or create worker engine (lazy initialization)."""
    global _worker_engine
    if _worker_engine is None:
        _worker_engine = create_async_engine(...)
    return _worker_engine

def get_worker_session() -> AsyncSession:
    """Get a worker database session."""
    global _worker_session_factory
    if _worker_session_factory is None:
        _worker_session_factory = async_sessionmaker(_get_worker_engine(), ...)
    return _worker_session_factory()

def get_worker_redis_client() -> RedisClientProtocol:
    """Get the worker's shared Redis client."""
    global _worker_redis_client
    if _worker_redis_client is None:
        _worker_redis_client = redis.asyncio.from_url(...)
    return _worker_redis_client
```

### 2. tasks.py - Run in Worker Loop

```python
def run_in_worker_loop[T](
    coro_func: Callable[..., Awaitable[T]],
    *args: Any,
    **kwargs: Any,
) -> T:
    """Run an async function in the worker's persistent event loop."""
    loop = asyncio.get_event_loop()  # Get worker's persistent loop
    coro = coro_func(*args, **kwargs)
    return loop.run_until_complete(coro)

@celery_app.task(bind=True, max_retries=3)
def check_disruptions_and_alert(self: BoundTask) -> DisruptionCheckResult:
    """Check for TfL disruptions and send alerts."""
    try:
        result = run_in_worker_loop(_check_disruptions_async)
        return result
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60) from exc

async def _check_disruptions_async() -> DisruptionCheckResult:
    """Async implementation of disruption checking."""
    session = None
    try:
        # Get shared resources - no per-task reset needed
        session = get_worker_session()
        redis_client = get_worker_redis_client()  # Shared client

        alert_service = AlertService(db=session, redis_client=redis_client)
        result = await alert_service.process_all_routes()
        return result
    finally:
        # Close session only - Redis client lifecycle managed by worker
        if session is not None:
            await session.close()
```

## Key Improvements Over Previous Implementation

1. **No per-task loop creation/destruction** - Event loop persists for worker lifetime
2. **No per-task engine reset** - Engine persists and is shared across tasks
3. **Connection pool reuse** - Database connections are properly pooled across tasks
4. **Shared Redis client** - Redis client is reused across tasks in same worker
5. **Proper cleanup** - Resources are disposed during worker shutdown

## Resource Lifecycle

```
Worker Process Lifecycle:
┌─────────────────────────────────────────────────────────┐
│ worker_process_init signal                              │
│   └─ Create persistent event loop                       │
├─────────────────────────────────────────────────────────┤
│ Task 1: check_disruptions_and_alert()                   │
│   └─ run_in_worker_loop(_check_disruptions_async)       │
│       └─ Uses persistent loop                           │
│       └─ Creates engine (first access, lazy init)       │
│       └─ Creates Redis client (first access, lazy init) │
│       └─ Creates session (per task)                     │
│       └─ Closes session (per task)                      │
├─────────────────────────────────────────────────────────┤
│ Task 2: rebuild_route_indexes_task()                    │
│   └─ run_in_worker_loop(_rebuild_indexes_async)         │
│       └─ Uses same persistent loop                      │
│       └─ Uses same engine (connection pool)             │
│       └─ Creates session (per task)                     │
│       └─ Closes session (per task)                      │
├─────────────────────────────────────────────────────────┤
│ ... more tasks ...                                      │
├─────────────────────────────────────────────────────────┤
│ worker_process_shutdown signal                          │
│   └─ Dispose engine (closes all pooled connections)     │
│   └─ Close Redis client                                 │
│   └─ Close event loop                                   │
└─────────────────────────────────────────────────────────┘
```

## Trade-offs

**Pros:**
- Complete event loop consistency across tasks
- Connection pooling actually works (shared engine)
- No asyncpg errors or event loop conflicts
- Faster task execution (no per-task loop creation overhead)
- Redis client reused (no per-task connection overhead)

**Cons:**
- Shared engine means if one task corrupts state, subsequent tasks are affected
- Must ensure sessions are properly closed (session lifecycle still per-task)
- More complex shutdown handling (must dispose resources before closing loop)

## Files Changed

- `backend/app/celery/database.py` - Persistent loop with lazy resource initialization
- `backend/app/celery/tasks.py` - Simplified `run_in_worker_loop()`, removed `reset_worker_engine()` calls
- `backend/tests/test_celery_tasks.py` - Updated mocks to patch `run_in_worker_loop` and `get_worker_redis_client`
- `backend/tests/test_celery_database_integration.py` - Added lifecycle tests for init/cleanup
- `docs/adr/08-background-jobs.md` - Documented updated decision

## References

- Issue #195: https://github.com/mnbf9rca/IsTheTubeRunning/issues/195
- Issue #190: https://github.com/mnbf9rca/IsTheTubeRunning/issues/190 (original event loop errors)
- Issue #147: https://github.com/mnbf9rca/IsTheTubeRunning/issues/147 (original fork safety implementation)
- SQLAlchemy docs: [Using Connection Pools with Multiprocessing](https://docs.sqlalchemy.org/en/20/core/pooling.html#using-connection-pools-with-multiprocessing-or-os-fork)
- Celery signals: [worker_process_init](https://docs.celeryq.dev/en/stable/userguide/signals.html#worker-process-init)
