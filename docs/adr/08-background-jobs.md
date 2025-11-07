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
