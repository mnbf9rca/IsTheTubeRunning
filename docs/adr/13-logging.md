# Structured Logging

## structlog with stdlib Bridge

### Status
Active

### Context
The application uses structlog for structured logging, but third-party libraries (aiocache, Celery, urllib3, OpenTelemetry) use Python's standard logging module. Without proper integration, these logs appear unformatted and inconsistent with application logs.

### Decision
Use structlog's `ProcessorFormatter` with `foreign_pre_chain` to route ALL logs through the same processing pipeline.

### Alternatives Considered
- **Separate formatters for stdlib and structlog**: Would result in inconsistent log formats
- **Replace stdlib usage in libraries**: Not feasible for third-party code
- **Custom wrapper around stdlib**: More complex and fragile

### Consequences

**Easier:**
- All logs have consistent structured format
- Third-party library logs are properly formatted
- Log level is configurable via environment variable
- Single source of truth for log configuration

**More Difficult:**
- Must ensure `configure_logging()` is called early in process startup
- Cannot use print() for debugging (won't be structured)

---

## Event-Style Logging Pattern

### Status
Active

### Context
Need a consistent pattern for logging that enables searchability and parsing by log aggregators.

### Decision
Use event names (snake_case) as the first argument with context as keyword arguments. This enables searching logs by event name and parsing structured data.

### Alternatives Considered
- **Format strings**: Lose structure, harder to parse and search
- **JSON-only messages**: Less human-readable during development

### Consequences

**Easier:**
- Logs are searchable by event name
- Context data is easily parsed by log aggregators
- Consistent pattern across codebase

**More Difficult:**
- Requires discipline to use event names consistently
- More verbose than simple string messages

---

## Third-Party Logger Noise Reduction

### Status
Active

### Context
Third-party libraries produce verbose logs at INFO/DEBUG level (Redis GET/SET, HTTP connection details) that clutter output and make application logs harder to find.

### Decision
Set specific third-party loggers to WARNING level to reduce noise while preserving important warnings and errors.

### Alternatives Considered
- **Disable entirely**: Would lose valuable error/warning information
- **Leave at INFO**: Too much noise obscures application logs
- **Per-request filtering**: Too complex for limited benefit

### Consequences

**Easier:**
- Cleaner log output focused on application events
- Important warnings/errors still visible

**More Difficult:**
- May miss useful INFO-level logs during debugging
- Need to temporarily adjust levels when debugging library issues

---

## Celery Worker Logging Configuration

### Status
Active

### Context
Celery workers fork from the main process and need their own logging configuration. Without explicit configuration, workers use Celery's default unstructured logging.

### Decision
Configure logging at Celery app module load time (before tasks run) and disable Celery's root logger hijacking to prevent it from overriding our configuration.

### Alternatives Considered
- **Per-task configuration**: Redundant and error-prone
- **Celery's built-in formatters**: Don't integrate with structlog
- **Configure in worker_process_init signal**: Too late, some logs already emitted

### Consequences

**Easier:**
- Workers have consistent logging with API processes
- No special per-task logging configuration needed

**More Difficult:**
- Must ensure configuration happens at import time
- Cannot change log level without restarting workers

---

## Access Logging with OTEL Trace Correlation

### Status
Active

### Context
Uvicorn's default access logs are unformatted and don't include OpenTelemetry trace IDs, making it difficult to correlate HTTP requests with distributed traces in observability tools.

### Decision
Use custom Starlette middleware for access logging that goes through structlog and automatically includes OTEL trace/span IDs. Silence uvicorn's access logger since it's replaced by this middleware.

### Alternatives Considered
- **asgi-correlation-id package**: Uses separate correlation IDs, not compatible with OTEL trace IDs
- **Suppress uvicorn logs only**: Would lose access logging entirely
- **Custom uvicorn logger**: More complex, still wouldn't integrate with structlog pipeline

### Consequences

**Easier:**
- Correlate HTTP requests with distributed traces in Grafana
- Consistent structured format for all access logs
- Client IP extraction handles proxy headers

**More Difficult:**
- Uvicorn startup logs still unformatted (before app middleware runs)
- Must add middleware to FastAPI app configuration

---

## Related ADRs

- [08. Background Jobs & Workers](./08-background-jobs.md) - Celery configuration
- [12. Observability & Distributed Tracing](./12-observability.md) - OpenTelemetry integration
