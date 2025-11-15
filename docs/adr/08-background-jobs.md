# Background Jobs & Workers

## Celery + Redis

### Status
Active

### Context
Alert processing (checking TfL disruptions and sending notifications) must run in background on schedule. Need reliable, scalable job queue.

### Decision
Use Celery with Redis broker. Celery Beat for scheduled tasks (every 30s). Separate worker container from FastAPI app.

### Consequences
**Easier:**
- Proper async job handling (non-blocking)
- Scalable (can add more workers)
- Reliable (Redis ensures task durability)
- Industry standard (well-documented)
- Scheduled tasks built-in (Celery Beat)

**More Difficult:**
- Additional infrastructure (Redis, Celery worker container)
- More complex monitoring (need to monitor worker health)
- Debugging can be harder (tasks run in separate process)

---

## Content-Based Alert Deduplication

### Status
Active

### Context
Disruptions can persist for hours or days. Sending the same alert repeatedly would spam users. But if disruption status changes (e.g., "minor delays" → "severe delays"), users should be notified.

### Decision
Track last alert state in Redis (key: `last_alert:{route_id}:{user_id}`) with SHA256 hash of disruption details (line_id, status_severity_description, reason). Only send new alert if content changed. TTL: 7 days for auto-cleanup.

### Consequences
**Easier:**
- Prevents alert spam (same disruption = no new alert)
- Users informed of status changes (content hash changes = new alert)
- Fast lookups (Redis key-value)
- Automatic cleanup (7-day TTL)

**More Difficult:**
- Depends on Redis for state (if Redis is flushed, may re-send alerts)
- Need to serialize disruption details consistently for hashing
- Status changes that don't change hash won't trigger new alert

---

## Hybrid Task Scheduling

### Status
Active

### Context
Want to check for disruptions frequently (responsive alerts) but don't want to spam TfL API. TfL data is cached with 2-minute TTL.

### Decision
Celery Beat runs disruption check task every 30 seconds, but TfL data fetch respects cache layer TTL (typically 2 minutes). Task timeout: 5 min hard limit, 4 min soft limit to prevent runaway tasks.

### Consequences
**Easier:**
- Dynamic scheduling without complex logic
- Responsive to cache expiry (checks when cache is likely stale)
- Minimizes redundant API calls (cache layer prevents excess calls)
- Fast response to disruptions (30s granularity)

**More Difficult:**
- Task scheduling depends on cache behavior (less explicit)
- Must ensure cache TTL is reasonable (too long = stale data)

---

## Worker Database Sessions

### Status
Active

### Context
Celery workers need database access but share the same database as FastAPI app. Connection pool conflicts can occur if both use the same engine.

### Decision
Celery workers use separate async SQLAlchemy engine/session factory from FastAPI app. Uses NullPool in tests for isolation, QueuePool in production for connection reuse. Workers get sessions via `get_worker_session()` helper with proper cleanup.

**See also:** "Worker Pool Fork Safety" below for how connection pooling is handled across forked worker processes.

### Consequences
**Easier:**
- Prevents connection pool conflicts
- Workers and app can scale independently
- Clear separation of concerns
- Proper connection cleanup in workers

**More Difficult:**
- Must maintain two database engines (app, worker)
- More complex configuration
- Need to ensure both engines use correct pool settings

---

## Worker Pool Fork Safety

### Status
Active (Implemented 2025-11-14, Issue #147)

### Context
Celery workers using fork pool with SQLAlchemy async engine experience asyncpg InterfaceError ("cannot perform operation: another operation is in progress") and RuntimeError ("Future attached to a different loop"). Root cause: SQLAlchemy's async engine creates asyncio.Queue objects bound to the event loop that created them. With forked workers and per-task event loops, these Queue objects become bound to the wrong loop.

**Related ADRs:**
- ADR 10 "NullPool for Async Test Isolation" - Similar event loop binding issue in pytest-asyncio

### Decision
Use lazy engine initialization with per-task reset:
1. Defer engine creation until first access (not at module import time)
2. Reset engine globals at start of each task to force fresh engine creation
3. Reset event loop policy after worker fork

This ensures each task's engine binds asyncio primitives to the correct event loop.

See `docs/celery-fork-safety.md` for implementation details.

### Consequences
**Easier:**
- Connection pooling works in all environments without conditional logic
- Complete event loop isolation between tasks and workers
- No asyncpg InterfaceError or event loop conflicts

**More Difficult:**
- Engine recreated per task (small overhead, necessary for correctness)
- Must call `reset_worker_engine()` at start of each new async task function
- More complex initialization pattern than simple import-time creation

---

## FastAPI Worker Fork Safety

### Status
Active (Implemented 2025-11-15, Issue #151)

### Context
FastAPI deployed with multiple uvicorn workers (`--workers > 1`) uses `os.fork()` to create worker processes. Similar to Celery workers, if SQLAlchemy async engine is created at module import time, forked workers inherit the parent's engine with asyncio primitives (Queue objects) bound to the parent's event loop. This can cause asyncpg InterfaceError and RuntimeError when workers try to use the inherited engine.

**Key Difference from Celery:** FastAPI workers use the same event loop for all requests within a worker process. They do NOT create a fresh event loop per request. This makes the fork safety solution simpler than Celery's.

**Related ADRs:**
- ADR 08 "Worker Pool Fork Safety" (Celery) - Similar issue, more complex solution
- ADR 10 "NullPool for Async Test Isolation" - Event loop binding in pytest-asyncio

### Decision
Use lazy engine initialization only (no per-request reset needed):
1. Module-level `_engine` and `_session_factory` globals initialized to None
2. `get_engine()` function creates engine on first access
3. `get_session_factory()` function creates session factory on first access
4. `get_db()` dependency uses `get_session_factory()` instead of global import

This prevents forked worker processes from inheriting the parent's engine. Each worker creates its own engine when first accessed, binding asyncio primitives to the worker's event loop.

**Implementation:**
```python
# app/core/database.py
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None

def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        if settings.DEBUG:
            _engine = create_async_engine(
                settings.DATABASE_URL,
                echo=settings.DATABASE_ECHO,
                poolclass=NullPool,
            )
        else:
            _engine = create_async_engine(
                settings.DATABASE_URL,
                echo=settings.DATABASE_ECHO,
                pool_size=settings.DATABASE_POOL_SIZE,
                max_overflow=settings.DATABASE_MAX_OVERFLOW,
            )
    return _engine
```

**Why no per-request reset?** Unlike Celery tasks which use `run_in_isolated_loop()` (fresh event loop per task), FastAPI workers use one event loop for all requests in that worker process. The engine only needs to bind to the worker's event loop once.

### Consequences
**Easier:**
- Safe deployment with multiple uvicorn workers (`--workers > 1`)
- Consistent fork safety pattern across FastAPI and Celery
- Production-ready with connection pooling (`pool_size`, `max_overflow`)
- Single-process development still works (engine created on first request)
- Simpler than Celery solution (no per-request reset needed)

**More Difficult:**
- One additional function call per engine access (`get_engine()` instead of `engine`)
- Must import `get_engine()` instead of `engine` directly
- Slightly more complex than import-time initialization

---

## Route Index Rebuilding Strategy

### Status
Active

### Context
Route station indexes enable O(log n) lookup for disruption matching. Building indexes involves expanding sparse route segments to complete station lists (50-100ms per route). Need balance between consistency (index matches route data) and performance (fast API responses).

### Decision
Hybrid approach: synchronous for route CRUD operations (part of same transaction with `auto_commit=False`), asynchronous Celery task for bulk admin rebuilds. Route changes trigger immediate index rebuild within the transaction; admin bulk operations use `rebuild_route_indexes_task()`.

### Consequences
**Easier:**
- Transactional safety (route + index are atomic, rollback on failure)
- Fast API responses for route changes (<100ms including index rebuild)
- Immediate consistency (no window where route exists without index)
- Bulk rebuilds don't block API (run in background via Celery)
- Automatic rebuild on every route change (no stale indexes)

**More Difficult:**
- Small latency cost on route CRUD operations (50-100ms per route)
- Two code paths for rebuilding (sync vs async)
- Must ensure both paths use same underlying service method

---

## Event-Driven Staleness Detection for Route Indexes

### Status
Active

### Context
Route station indexes store a `line_data_version` timestamp (copy of `Line.last_updated`) to track when the index was built. TfL line data changes over time as route sequences are updated (stations added/removed/reordered). Stale indexes reference outdated TfL data, causing inaccurate alert matching. Need automatic detection and rebuild without manual intervention.

### Decision
Event-driven Celery task (`detect_and_rebuild_stale_routes`) triggered immediately after TfL station graph is rebuilt via `POST /admin/tfl/build-graph`. Task queries for routes where `index.line_data_version < Line.last_updated`, then triggers individual `rebuild_route_indexes_task.delay(route_id)` for each stale route.

**Implementation:**
- **Trigger point:** API layer orchestration in `/admin/tfl/build-graph` endpoint after successful graph build
- **Pure helper function:** `find_stale_route_ids(session)` performs staleness query with DISTINCT to avoid duplicates
- **Query pattern:** `SELECT DISTINCT route_id FROM route_station_index JOIN route_segments JOIN lines WHERE line_data_version < Line.last_updated`
- **Execution strategy:** Trigger individual rebuild tasks (parallelization + fault isolation)
- **Non-blocking:** Task is queued synchronously (~1ms) but executes asynchronously in Celery worker
- **Structured logging:** Logs stale route count, triggered count, partial failures

### Consequences
**Easier:**
- **Zero manual intervention:** Indexes stay accurate automatically when TfL data changes
- **Immediate response:** No delay between TfL update and index rebuild (event-driven, not scheduled)
- **Efficient:** Only runs when TfL data actually changes (not wasted daily checks)
- **Efficient detection:** Single query finds all stale routes across all lines
- **Leverages existing infrastructure:** Reuses tested `rebuild_route_indexes_task()`
- **Parallelization:** Individual rebuild tasks can run concurrently across workers
- **Fault isolation:** One route rebuild failure doesn't block others
- **Monitoring-friendly:** Structured logging for Sentry/alerting integration
- **API layer orchestration:** Service stays focused, API controls workflow

**More Difficult:**
- **Requires Line.last_updated tracking:** Depends on TfL service updating this field when fetching line data
- **Potential for mass rebuilds:** If many lines update simultaneously, many routes rebuild at once (mitigated by Celery's task queue buffering)
- **Depends on admin triggering graph build:** Detection only runs when admin updates TfL data (acceptable - admin endpoint `/admin/routes/rebuild-indexes` available for manual override if needed)

---

## Inverted Index for Alert Matching

### Status
Active

### Context
Original implementation matched disruptions to routes using line-level filtering only. This caused false positives: ALL routes on a line were alerted even if disruption only affected a specific section (e.g., Piccadilly line disruption at Russell Square → Holborn would alert Earl's Court → Heathrow routes on western branch). With 1000+ routes, this doesn't scale (O(routes × disruptions) complexity).

### Decision
Use inverted index (`route_station_index` table) for station-level matching. Index maps `(line_tfl_id, station_naptan)` → `route_id` for ALL intermediate stations (expanded from sparse user input). Alert matching queries index for each affected (line, station) combination and returns union of matching route IDs.

**Algorithm:**
1. If `disruption.affected_routes` exists (station-level data from TfL):
   - Extract `(line_tfl_id, station_naptan)` pairs using pure function `extract_line_station_pairs()`
   - Query index for each pair: `SELECT route_id WHERE line_tfl_id=X AND station_naptan=Y`
   - Return union of all matching route_ids (automatic deduplication via set)
2. Else (no station data - RARE):
   - Fall back to line-level matching
   - Log warning (indicates missing TfL data)

**Complexity:** O(affected_stations × log(index_size)), NOT O(routes × disruptions) - key optimization!

### Consequences
**Easier:**
- **NO false positives:** Only routes passing through affected stations are alerted
- **Minimal false negatives:** All affected routes with populated indexes are found via station-level lookup. Routes without index entries (e.g., newly created before index is built) fall back to line-level matching using segments
- **Branch disambiguation works automatically:** Different branches = different station sets
- **Scales to 100k+ routes:** Performance independent of total route count
- **Fast queries:** < 100ms for 1000 routes + 10 disruptions (verified via performance tests)
- **Pure function design:** `extract_line_station_pairs()` is testable without database
- **Fallback resilience:** Graceful degradation to line-level when TfL data incomplete
- **Warning logging:** Fallback path logs warning for monitoring

**More Difficult:**
- **Depends on index completeness:** Routes without index entries won't match (mitigated by automatic index building on route create/update)
- **Two matching paths:** Index-based (preferred) vs line-level fallback (rare)
- **TfL data dependency:** Requires `disruption.affected_routes` data from TfL API (currently available for most disruption types)
