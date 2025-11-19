# Observability & Distributed Tracing

## OpenTelemetry for Distributed Tracing

### Status
Active

### Context
Operating a distributed system (FastAPI backend, Celery workers, PostgreSQL, Redis) without observability is challenging:
- Difficult to debug performance issues ("why is this API call slow?")
- No visibility into database query performance
- Hard to correlate errors across services
- Manual log analysis is time-consuming and error-prone

Need structured observability to:
- Trace requests across services (API → DB → Celery)
- Identify performance bottlenecks
- Debug production issues quickly
- Monitor system health

### Decision
Use OpenTelemetry (OTEL) for distributed tracing with OTLP protocol to send traces to Grafana Cloud.

**Scope:**
- FastAPI endpoint tracing
- SQLAlchemy database query tracing
- Celery worker task tracing with context propagation
- TfL API call tracing with custom spans (Issue #174)
- OTLP HTTP export to Grafana Cloud
- Log-trace correlation (structlog with trace_id/span_id)

**Deferred:**
- Metrics collection
- Frontend browser tracing

### TfL API Instrumentation

Custom spans are created for all TfL API calls with the following naming convention:

```
tfl.api.<endpoint_name>
```

**Span Attributes:**
- `tfl.api.endpoint` - API method name (e.g., "MetaModes", "GetByModeByPathModes")
- `tfl.api.client` - Client type ("line_client" or "stoppoint_client")
- `tfl.api.mode` - Transport mode when applicable (e.g., "tube", "dlr")
- `tfl.api.line_id` - Line ID when applicable (e.g., "victoria")
- `tfl.api.direction` - Direction when applicable ("inbound" or "outbound")
- `peer.service` - Always "api.tfl.gov.uk"
- `http.status_code` - HTTP response status code

**Instrumented Methods:**
- `fetch_available_modes()` - MetaModes
- `fetch_lines()` - GetByModeByPathModes (per mode)
- `fetch_severity_codes()` - MetaSeverity
- `fetch_disruption_categories()` - MetaDisruptionCategories
- `fetch_stop_types()` - MetaStopTypes
- `_extract_hub_fields()` - GetByPathIdsQueryIncludeCrowdingData
- `_fetch_stations_from_api()` - StopPointsByPathIdQueryTflOperatedNationalRailStationsOnly
- `fetch_line_disruptions()` - StatusByIdsByPathIdsQueryDetail
- `fetch_station_disruptions()` - DisruptionByModeByPathModesQueryIncludeRouteBlockedStops (per mode)
- `_fetch_route_sequence()` - RouteSequenceByPathIdPathDirectionQueryServiceTypesQueryExcludeCrowding

**Why OpenTelemetry?**
- **Industry Standard**: Vendor-neutral, CNCF project with wide adoption
- **Rich Ecosystem**: Auto-instrumentation for FastAPI, SQLAlchemy, Celery, Redis, etc.
- **Backend Agnostic**: Can switch from Grafana Cloud to Jaeger, Honeycomb, Datadog without code changes
- **Future-Proof**: Supports traces, metrics, and logs in one SDK

**Why OTLP (OpenTelemetry Protocol)?**
- Vendor portability (no lock-in to Grafana)
- Standard protocol supported by all major observability platforms
- Efficient wire format (HTTP/Protobuf)

**Why Grafana Cloud?**
- Free tier: 50GB traces/month, 14-day retention (sufficient for hobby project)
- Integrated with Loki (logs) and Prometheus (metrics) for future expansion
- Familiar Grafana UI for visualization
- OTLP native support (no vendor-specific SDK needed)

**Why Traces Only (not Metrics)?**
- **Highest ROI**: Traces provide immediate value for debugging API performance
- **Auto-Generated Metrics**: Grafana auto-generates RED metrics (Rate, Errors, Duration) from trace data
- **YAGNI Principle**: Metrics collection can be added later if needed
- **Simplicity**: Start simple, add complexity only when justified

**Why Defer Frontend Tracing?**
- Backend priority (API performance is more critical than frontend)
- Browser tracing is experimental/immature compared to backend
- Limited value for hobby project (frontend is simple, API is complex)
- Can add later if frontend performance becomes a concern

### Consequences

**Easier:**
- **Debug Production Issues**: Trace requests from API entry → DB queries → Celery tasks
- **Identify Slow Queries**: See exact SQL statements with execution time
- **Find Performance Bottlenecks**: Visual flamegraphs show where time is spent
- **Correlate Errors**: Traces link errors across services
- **Monitor Without Code Changes**: Auto-instrumentation requires minimal code
- **Vendor Flexibility**: Can switch observability backends without changing application code

**More Difficult:**
- **Additional Infrastructure**: Requires Grafana Cloud account and OTLP endpoint configuration
- **Configuration Management**: Need to secure and rotate OTLP auth token in `.env.vault`
- **Learning Curve**: Team needs to learn OTEL concepts (spans, traces, context propagation)
- **Overhead**: Minimal (<5ms latency, <1% CPU) but not zero
- **Test Complexity**: Tests need special handling to disable OTEL
- **Dependency on External Service**: If Grafana Cloud is down, traces are lost (not critical for hobby project)

---

## FastAPI Instrumentation Pattern

### Status
Active (Issue #210)

### Context
OpenTelemetry's `FastAPIInstrumentor` must wrap the ASGI application to intercept HTTP requests and create trace spans. The instrumentor needs access to the FastAPI app instance to modify its middleware stack.

**Problem**: Calling `FastAPIInstrumentor().instrument()` at module level (before app creation) prevents the instrumentor from wrapping the app, resulting in no HTTP request spans being created.

**Symptoms**:
- Incoming API requests don't generate parent trace spans
- Downstream operations (DB queries, Redis, external APIs) create separate root traces with different trace IDs
- Service graph shows disconnected operations instead of request → dependency flow
- Cannot correlate operations back to the API request that triggered them

### Decision
Instrument FastAPI using `instrument_app(app)` after app instantiation, not using automatic `instrument()` at module level.

**Pattern**:
```python
# main.py

# Create app first
app = FastAPI(
    title="IsTheTubeRunning API",
    description="TfL Disruption Alert System Backend",
    version=__version__,
    lifespan=lifespan,
)

# Then instrument (module level, after app exists)
if settings.OTEL_ENABLED:
    FastAPIInstrumentor().instrument_app(
        app,
        excluded_urls=",".join(settings.OTEL_EXCLUDED_URLS),
    )
    logger.info("otel_fastapi_instrumented", excluded_urls=settings.OTEL_EXCLUDED_URLS)

# TracerProvider is set later in lifespan (after fork) for fork-safety
```

**Key Points**:
1. App must exist before instrumentation
2. Use `instrument_app(app)` not `instrument()` for explicit control
3. TracerProvider still set in lifespan for fork-safety (instrumentation just patches middleware)
4. Excluded URLs (health/metrics) configured at instrumentation time

### Consequences

**Easier:**
- HTTP request spans are properly created as root spans
- Downstream operations (DB, Redis, external APIs) become child spans
- Complete trace hierarchy enables end-to-end request tracing
- Service graph shows proper topology: Client → FastAPI → [PostgreSQL, Redis, TfL API]
- Log-trace correlation works correctly (same trace_id across all operations)

**More Difficult:**
- Must remember to instrument after app creation (pattern is less obvious)
- Can't rely on automatic discovery (more explicit code)

### Verification
Tests verify the instrumentation pattern in `tests/test_otel_integration.py`:
- `test_fastapi_instrumentation_pattern` - Verifies app loads with OTEL enabled
- `test_fastapi_not_instrumented_when_otel_disabled` - Verifies instrumentation is NOT applied when OTEL disabled
- `test_fastapi_spans_with_real_request` - Verifies HTTP requests create parent spans and downstream operations share same trace_id

---

## Service Name Differentiation

### Status
Active

### Context
Multiple components (FastAPI API, Celery Worker, Celery Beat) share the same codebase but run as separate processes. Without differentiation, all components appear as a single service node in Grafana service graphs, making it impossible to visualize the actual service topology and trace flow between components.

### Decision
Use environment variable `OTEL_SERVICE_NAME` to differentiate components in service graphs:
- **FastAPI/Backend**: `isthetuberunning-api`
- **Celery Worker**: `isthetuberunning-worker`
- **Celery Beat**: `isthetuberunning-beat`

Set via Docker Compose environment variables for containerized deployment. Default value in `.env` is `isthetuberunning-backend` for local development simplicity.

### Consequences
**Easier:**
- Clear service graph topology (API → Redis → Worker → PostgreSQL)
- Identify bottlenecks per component (API vs Worker latency)
- Correlate traces across component boundaries
- Debugging which component is slow or failing

**More Difficult:**
- Must configure `OTEL_SERVICE_NAME` per Docker service
- Local dev defaults to single service name (less visibility)

---

## Redis Instrumentation

### Status
Active

### Context
Redis is used for Celery broker operations, task result storage, and caching. Without Redis instrumentation, these operations are invisible in traces, making it difficult to debug broker/cache performance issues.

### Decision
Use `opentelemetry-instrumentation-redis` to auto-instrument all Redis operations. The `RedisInstrumentor().instrument()` call patches the redis module globally during TracerProvider initialization.

**Instrumented Operations:**
- Celery broker operations (task dispatch, result retrieval)
- Cache operations (if using Redis backend)
- Alert deduplication state storage

**Semantic Conventions:**
- `db.system`: "redis"
- `db.statement`: Redis command
- `net.peer.name`: Redis host
- `net.peer.port`: Redis port

### Consequences
**Easier:**
- Visibility into Celery broker latency
- Debug slow cache operations
- Identify Redis connection issues
- Complete service graph with Redis node

**More Difficult:**
- Additional dependency (`opentelemetry-instrumentation-redis`)
- More spans generated (may increase OTLP data volume)

---

## Celery Beat Instrumentation

### Status
Active

### Context
Celery Beat scheduler runs as a separate process from Celery workers. Without OTEL initialization, Beat-triggered tasks don't have proper trace context, breaking the trace chain from scheduled trigger to task execution.

### Decision
Initialize TracerProvider in Beat process via `beat_init` Celery signal. This mirrors the worker pattern in `worker_process_init` for consistency.

**Implementation:**
```python
@beat_init.connect
def init_beat_otel(**kwargs):
    if settings.OTEL_ENABLED:
        from app.core.telemetry import get_tracer_provider
        if provider := get_tracer_provider():
            trace.set_tracer_provider(provider)
```

### Consequences
**Easier:**
- Beat scheduler appears in service graph
- Scheduled tasks have proper trace context
- Consistent OTEL initialization pattern across all components

**More Difficult:**
- Additional signal handler to maintain
- Beat-specific testing required

---

### Related ADRs
- **ADR 08**: Worker Pool Fork Safety (Celery worker lazy initialization)
- **ADR 10**: Testing Strategy (test coverage and mocking approach)
- **ADR 02**: Development Tools (dependency management)
