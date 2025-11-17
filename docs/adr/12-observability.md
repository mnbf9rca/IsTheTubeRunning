# Observability & Distributed Tracing

## OpenTelemetry for Distributed Tracing

### Status
Active (Implemented 2025-11-17, Issue #172)

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

**Phase 1 (MVP - Issue #172):**
- Instrument FastAPI endpoints (HTTP request tracing)
- Instrument SQLAlchemy (database query tracing)
- Export traces via OTLP HTTP to Grafana Cloud
- Backend only (no frontend, no Celery)

**Deferred to Phase 2:**
- Celery worker tracing (Issue #2)
- Custom application spans
- Metrics collection
- Frontend browser tracing

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

**Why Traces Only (Phase 1)?**
- **Highest ROI**: Traces provide immediate value for debugging API performance
- **Auto-Generated Metrics**: Grafana auto-generates RED metrics (Rate, Errors, Duration) from trace data
- **YAGNI Principle**: Metrics collection can be added later if needed
- **Simplicity**: Start simple, add complexity only when justified

**Why Defer Celery Instrumentation?**
- Separate concern (different process, different lifecycle)
- FastAPI/SQLAlchemy provides 80% of value for initial observability
- Celery instrumentation requires additional complexity (Issue #2)

**Why Defer Frontend Tracing?**
- Backend priority (API performance is more critical than frontend)
- Browser tracing is experimental/immature compared to backend
- Limited value for hobby project (frontend is simple, API is complex)
- Can add later if frontend performance becomes a concern

### Consequences

**Easier:**
- **Debug Production Issues**: Trace requests from API entry → DB queries → response
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

### Related ADRs
- **ADR 08**: Worker Pool Fork Safety (lazy initialization requirement)
- **ADR 10**: Testing Strategy (test coverage and mocking approach)
- **ADR 02**: Development Tools (dependency management)

### Future Enhancements (Post-MVP)
- **Issue #2**: Celery worker tracing (task-level spans)
- **Custom Spans**: TfL API calls, email sending, complex business logic
- **Metrics Collection**: RED metrics, custom business metrics
- **Log Correlation**: Inject trace IDs into structlog for log-trace correlation
- **Frontend Tracing**: Browser performance monitoring (if needed)
- **Alerting**: Grafana alerts for high latency or error rates
