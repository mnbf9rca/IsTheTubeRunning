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
- **NO false negatives:** All affected routes are found via index lookup
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
