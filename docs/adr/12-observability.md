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

## OTLP Log Export

### Status
Active (Issue #224)

### Context
While traces provide visibility into request flow and performance, logs contain detailed diagnostic information about application behavior, errors, and business logic. Without centralized log aggregation, debugging production issues requires SSH access to servers and manual log file inspection.

Current state:
- Structlog configured with JSON output and log-trace correlation (trace_id/span_id injection)
- Logs output to stdout only (container logs)
- No centralized log aggregation or search
- Trace context already added to logs via `_add_otel_context` processor

Need centralized logging to:
- Search logs across all services (API, Worker, Beat) from one interface
- Correlate logs with distributed traces using trace_id
- Analyze error patterns and trends
- Debug production issues without SSH access

### Decision
Export logs to Grafana Cloud Loki via OpenTelemetry OTLP protocol, using the same auth/endpoint as traces.

**Implementation:**
- LoggerProvider with lazy initialization (fork-safety pattern from ADR 08)
- OTLPLogExporter sends logs to Grafana Cloud Loki
- LoggingHandler bridges Python stdlib logging → OTEL logs
- Configurable log level for export via `OTEL_LOG_LEVEL` env var
- Custom filter removes non-serializable attributes (e.g., `_logger`)
- Separate OTLP endpoints for traces and logs

**Architecture:**
```
Structlog → stdlib logging → LoggingHandler → LoggerProvider → OTLPLogExporter → Grafana Cloud Loki
                         ↓
                    StreamHandler → stdout (preserved)
```

**Configuration:**
- `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT`: Grafana Cloud logs endpoint (e.g., `/otlp/v1/logs`)
- `OTEL_LOG_LEVEL`: Minimum log level to export (NOTSET, DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Same auth headers as traces (`OTEL_EXPORTER_OTLP_HEADERS`)

**Initialization Pattern:**
- FastAPI: LoggerProvider initialized in lifespan (after fork)
- Celery Worker: LoggerProvider initialized in `worker_process_init`
- Celery Beat: LoggerProvider initialized in `beat_init`
- Same lazy initialization pattern as TracerProvider for fork-safety

**Log-Trace Correlation:**
Already implemented via `_add_otel_context` processor:
- Every log event includes `trace_id` and `span_id` when inside a span
- Enables jumping from trace → logs in Grafana

### Consequences

**Easier:**
- **Centralized Log Search**: Query logs from all services in Grafana
- **Log-Trace Correlation**: Click trace_id in Grafana to see all related logs
- **Production Debugging**: Search errors without SSH access
- **Pattern Analysis**: Aggregate logs to find common issues
- **Service Context**: Logs tagged with service.name (API/Worker/Beat)
- **No New Dependencies**: OTLPLogExporter included in existing package

**More Difficult:**
- **Additional Handler**: Root logger has 2 handlers (stdout + OTLP)
- **Configuration**: Two separate endpoints (traces, logs) to manage
- **Volume Concerns**: Log export counts against Grafana Cloud quota (50GB/month free tier)
- **Filter Required**: Custom filter needed to remove non-serializable attributes
- **SDK Type Gaps**: LoggerProvider.shutdown() lacks type annotations (requires type: ignore)

### Testing
- Tests verify LoggingHandler added when OTEL enabled
- Tests verify handler NOT added when OTEL disabled
- Tests verify log level filtering works correctly
- Tests verify LoggerProvider fork-safety (lazy initialization)
- Tests verify graceful degradation when logs endpoint missing
- Coverage: 95.36% overall

---

## Explicit Span Status Pattern

### Status
Active (Issue #289)

### Context
OpenTelemetry spans have three possible status values:
- `UNSET` (default) - Status not explicitly set
- `OK` - Operation completed successfully
- `ERROR` - Operation failed with an error

By default, spans remain in `UNSET` state unless explicitly changed. While the SDK automatically sets `ERROR` status when exceptions occur, successful operations remain `UNSET` rather than `OK`. This makes it difficult to distinguish between:
- Operations that succeeded (should be `OK`)
- Operations where status was never set (programmer oversight)
- Operations that haven't completed yet

In Grafana, traces with `UNSET` status appear ambiguous and don't clearly indicate success.

### Decision
All custom spans must have explicit status:
- **Success**: Explicitly set `StatusCode.OK` on successful completion
- **Failure**: Let SDK automatically set `StatusCode.ERROR` when exceptions propagate

Use the `service_span` helper function from `app.core.telemetry` for all custom spans:

**Generic helper for all services:**
```python
from app.core.telemetry import service_span
from opentelemetry.trace import SpanKind

# For internal operations
with service_span("operation_name", "service-name") as span:
    # ... perform operation ...
    span.set_attribute("custom.attribute", value)
    # OK status set automatically on success
    # ERROR status set automatically on exception

# For external API calls
with service_span("api_call", "external-api", kind=SpanKind.CLIENT) as span:
    response = await make_api_call()
    span.set_attribute("http.status_code", response.status_code)
```

**Service-specific wrappers** (e.g., `tfl_api_span`) delegate to `service_span`:
```python
from app.core.telemetry import service_span

@contextmanager
def tfl_api_span(endpoint: str, client: str, **extra_attrs):
    """Wrapper around service_span with TfL-specific conventions."""
    with service_span(
        name=f"tfl.api.{endpoint}",
        service="api.tfl.gov.uk",
        kind=SpanKind.CLIENT,
        **{"tfl.api.endpoint": endpoint, "tfl.api.client": client, **extra_attrs},
    ) as span:
        yield span
```

### Implementation Details

The `service_span` helper (`backend/app/core/telemetry.py`) uses try/except to set status:
```python
with tracer.start_as_current_span(...) as span:
    try:
        yield span
        span.set_status(Status(StatusCode.OK))  # Success
    except Exception:
        # SDK records exception and sets ERROR status
        raise
```

### Consequences

**Easier:**
- **Clear Success Indication**: All successful operations show `OK` status in Grafana
- **Consistent Pattern**: `service_span` enforces explicit status across all services
- **Better Debugging**: Can immediately see which operations succeeded vs. failed
- **Service Graphs**: Grafana correctly shows success/error rates per service
- **Alerting**: Can alert on spans with `ERROR` status vs. `UNSET` ambiguity

**More Difficult:**
- **Migration Required**: Existing `tfl_api_span` needed refactoring to use `service_span`
- **Must Use Helper**: Direct `start_as_current_span` calls won't set status automatically
- **Import Required**: Services must import `service_span` from `app.core.telemetry`

### Testing
- `backend/tests/core/test_telemetry.py` - Tests for `service_span` helper
- `backend/tests/services/test_tfl_otel.py` - Tests verify `StatusCode.OK` on success
- `backend/tests/helpers/otel.py` - `assert_span_status()` helper for consistent assertions

### Files Modified
- `backend/app/core/telemetry.py` - Added `service_span` helper
- `backend/app/services/tfl_service.py` - Refactored `tfl_api_span` to use `service_span`
- `backend/tests/core/test_telemetry.py` - Tests for `service_span`
- `backend/tests/services/test_tfl_otel.py` - Success status tests
- `backend/tests/helpers/otel.py` - `assert_span_status()` helper

---

## PII Hashing in Logs and Telemetry

### Status
Active (Issue #311)

### Context
Application logs and OpenTelemetry traces originally contained plaintext PII (Personally Identifiable Information) such as email addresses and phone numbers. This created privacy and security concerns:
- Logs stored in Grafana Cloud contain user contact information
- Telemetry spans exposed PII in distributed tracing systems
- Difficult to link telemetry/logs back to specific users for debugging
- Compliance risk (GDPR, data minimization principles)

Examples of PII exposure:
- `logger.info("email_sent", recipient="user@example.com")`
- `span.set_attribute("email.recipient", "user@example.com")`

Need a consistent approach to protect PII while maintaining debuggability and user correlation.

### Decision
Hash all PII (email addresses, phone numbers) before logging or adding to telemetry spans using HMAC-SHA256 with a secret key.

**Implementation**:
1. **Centralized hash function** (`app.utils.pii.hash_pii()`):
   - Pure function using HMAC-SHA256, full 64-character hex digest
   - Deterministic: same input → same output given the same secret (enables correlation)
   - Keyed hash: uses `PII_HASH_SECRET` from configuration
   - Dictionary attack resistance: HMAC prevents precomputed rainbow tables
   - Fast: microseconds per hash
   - No collision risk: full 256-bit hash eliminates collisions

2. **Configuration**:
   - `PII_HASH_SECRET` setting in `backend/app/core/config.py` (required)
   - Secret stored in `.env` file (development) or environment variables (production)
   - Generate strong secret: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`

3. **Database storage**:
   - Added `contact_hash` column to `email_addresses` and `phone_numbers` tables
   - Indexed for fast lookups
   - Auto-computed on record creation via model `__init__`

4. **Logging pattern**:
   - Replace `recipient=value` with `recipient_hash=hash_pii(value)`
   - Replace `target=value` with `target_hash=hash_pii(value)`

5. **Telemetry pattern**:
   - Replace `email.recipient` with `email.recipient_hash`
   - Replace `sms.recipient` with `sms.recipient_hash`

**Changed services**:
- `email_service.py` - Logs and span attributes
- `sms_service.py` - Logs and span attributes (replaced inline hash)
- `notification_service.py` - Logs and span attributes (removed duplicate helper)
- `alert_service.py` - Logs
- `verification_service.py` - Rate limit storage

### Consequences

**Easier:**
- **Privacy Protection**: PII no longer stored in cleartext in logs/traces
- **Dictionary Attack Resistance**: HMAC with secret key prevents rainbow table attacks
- **User Correlation**: Can link logs/traces to users via hash lookup in database
- **Compliance**: Meets data minimization requirements
- **Consistency**: Single `hash_pii()` function used across all services
- **Debuggability**: Hash is deterministic - same user always produces same hash (given same secret)
- **Performance**: Indexed hash column enables fast reverse lookups

**More Difficult:**
- **Not Human-Readable**: Cannot immediately identify user from hash in logs
- **Requires Lookup**: Must query database to correlate hash → user
- **Secret Management**: Must securely manage `PII_HASH_SECRET` (rotation requires rehashing)
- **Migration**: Existing logs contain plaintext PII (cannot retroactively fix)

### Testing
- `backend/tests/utils/test_pii.py` - 8 tests for hash function (determinism, length, Unicode, case/whitespace sensitivity)
- Existing service tests updated to assert on `*_hash` attributes instead of raw values
- 100% coverage on new utility code

### Files Modified
- `backend/app/utils/pii.py` - Hash function
- `backend/app/models/user.py` - EmailAddress and PhoneNumber with contact_hash
- `backend/alembic/versions/xxx_add_contact_hash_columns.py` - Migration
- 5 service files updated (email, sms, notification, alert, verification)

---

### Related ADRs
- **ADR 08**: Worker Pool Fork Safety (Celery worker lazy initialization)
- **ADR 10**: Testing Strategy (test coverage and mocking approach)
- **ADR 02**: Development Tools (dependency management)
