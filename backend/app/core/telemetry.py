"""OpenTelemetry distributed tracing configuration."""

import threading
from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING

import structlog
from opentelemetry import trace
from opentelemetry._logs import set_logger_provider as otel_set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import SpanKind, Status, StatusCode

from app import __version__
from app.core.config import require_config, settings

if TYPE_CHECKING:
    from opentelemetry.trace.span import Span

logger = structlog.get_logger(__name__)

# Module-level globals for lazy initialization (fork-safety pattern from ADR 08)
_tracer_provider: TracerProvider | None = None
_tracer_provider_lock = threading.Lock()
_logger_provider: LoggerProvider | None = None
_logger_provider_lock = threading.Lock()
_redis_instrumented: bool = False


def get_tracer_provider() -> TracerProvider | None:
    """
    Get or create TracerProvider (lazy initialization for fork-safety).

    This function uses lazy initialization with double-checked locking to ensure
    each forked worker process creates its own TracerProvider. This prevents
    event loop binding issues when uvicorn uses multiple workers.

    Returns:
        TracerProvider if OTEL is enabled, None otherwise

    Note:
        - Returns None if OTEL_ENABLED=false (graceful degradation)
        - Each worker creates its own provider after fork
        - Thread-safe singleton pattern within each worker
    """
    if not settings.OTEL_ENABLED:
        return None

    global _tracer_provider  # noqa: PLW0603  # Required for lazy singleton pattern (ADR 08)
    if _tracer_provider is None:
        with _tracer_provider_lock:
            if _tracer_provider is None:  # Double-checked locking
                _tracer_provider = _create_tracer_provider()
    return _tracer_provider


def _create_tracer_provider() -> TracerProvider:
    """
    Create and configure TracerProvider (internal helper).

    Validates configuration and creates TracerProvider with OTLP exporter.
    Only called by get_tracer_provider() with thread safety guarantees.

    Returns:
        Configured TracerProvider

    Raises:
        ValueError: If required OTLP endpoint is missing in production
    """
    # Production mode requires OTLP endpoint for traces
    if not settings.DEBUG:
        require_config("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")

    # Create resource with service metadata
    resource = Resource(
        attributes={
            "service.name": settings.OTEL_SERVICE_NAME,
            "service.version": __version__,
            "deployment.environment": settings.OTEL_ENVIRONMENT,
        }
    )

    # Create provider
    provider = TracerProvider(resource=resource)

    # Instrument Redis for distributed tracing
    # RedisInstrumentor patches the redis module globally, so only call once
    # Note: This code is protected by _tracer_provider_lock via get_tracer_provider()
    # which is the only caller of this private function (see docstring above)
    global _redis_instrumented  # noqa: PLW0603  # Required for instrumentation tracking
    if not _redis_instrumented:
        try:
            RedisInstrumentor().instrument()
            _redis_instrumented = True
            logger.debug("redis_instrumented_for_otel")
        except Exception:
            logger.exception("redis_instrumentation_failed")
            # Continue without Redis instrumentation - graceful degradation

    # Add OTLP exporter if endpoint is configured
    if settings.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT:
        # Parse OTLP headers (format: "key1=value1,key2=value2")
        headers = _parse_otlp_headers(settings.OTEL_EXPORTER_OTLP_HEADERS or "")

        # Create OTLP HTTP exporter
        otlp_exporter = OTLPSpanExporter(
            endpoint=settings.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT,
            headers=headers,
        )

        # Add batch processor for efficient span export
        span_processor = BatchSpanProcessor(otlp_exporter)
        provider.add_span_processor(span_processor)

        logger.info(
            "otel_tracer_provider_created",
            endpoint=settings.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT,
            service_name=settings.OTEL_SERVICE_NAME,
            environment=settings.OTEL_ENVIRONMENT,
        )
    else:
        logger.warning("otel_no_traces_endpoint_configured", message="traces will not be exported")

    return provider


def _parse_otlp_headers(headers_str: str) -> dict[str, str]:
    """
    Parse OTLP headers from comma-separated key=value pairs.

    Args:
        headers_str: Headers in format "key1=value1,key2=value2"

    Returns:
        Dictionary of parsed headers

    Example:
        >>> _parse_otlp_headers("Authorization=Bearer token123,X-Custom=value")
        {'Authorization': 'Bearer token123', 'X-Custom': 'value'}
    """
    if not headers_str or not headers_str.strip():
        return {}

    headers = {}
    for raw_pair in headers_str.split(","):
        pair = raw_pair.strip()
        if "=" in pair:
            key, value = pair.split("=", 1)
            headers[key.strip()] = value.strip()
        elif pair:  # Non-empty string without equals sign
            logger.warning("otel_malformed_header", pair=pair)

    return headers


def shutdown_tracer_provider() -> None:
    """
    Shutdown TracerProvider gracefully.

    Flushes any pending spans and releases resources.
    Safe to call multiple times or when provider is None.
    """
    if _tracer_provider is not None:
        _tracer_provider.shutdown()
        logger.info("otel_tracer_provider_shutdown")


def get_logger_provider() -> LoggerProvider | None:
    """
    Get or create LoggerProvider (lazy initialization for fork-safety).

    This function uses lazy initialization with double-checked locking to ensure
    each forked worker process creates its own LoggerProvider. This prevents
    event loop binding issues when uvicorn uses multiple workers.

    Returns:
        LoggerProvider if OTEL is enabled, None otherwise

    Note:
        - Returns None if OTEL_ENABLED=false (graceful degradation)
        - Each worker creates its own provider after fork
        - Thread-safe singleton pattern within each worker
    """
    if not settings.OTEL_ENABLED:
        return None

    global _logger_provider  # noqa: PLW0603  # Required for lazy singleton pattern (ADR 08)
    if _logger_provider is None:
        with _logger_provider_lock:
            if _logger_provider is None:  # Double-checked locking
                _logger_provider = _create_logger_provider()
    return _logger_provider


def _create_logger_provider() -> LoggerProvider:
    """
    Create and configure LoggerProvider (internal helper).

    Validates configuration and creates LoggerProvider with OTLP exporter.
    Only called by get_logger_provider() with thread safety guarantees.

    Note:
        Unlike traces, logs can be useful even without OTLP export (stdout).
        Therefore, OTLP endpoint is optional even in production mode.

    Returns:
        Configured LoggerProvider
    """
    # Production mode doesn't require OTLP endpoint for logs (optional - logs can work without OTLP)
    # Note: Unlike traces, logs can be useful even without export (stdout)
    # So we don't require the endpoint in production

    # Create resource with service metadata (same as TracerProvider for correlation)
    resource = Resource(
        attributes={
            "service.name": settings.OTEL_SERVICE_NAME,
            "service.version": __version__,
            "deployment.environment": settings.OTEL_ENVIRONMENT,
        }
    )

    # Create provider
    provider = LoggerProvider(resource=resource)

    # Add OTLP exporter if endpoint is configured
    if settings.OTEL_EXPORTER_OTLP_LOGS_ENDPOINT:
        # Parse OTLP headers (same format as traces)
        headers = _parse_otlp_headers(settings.OTEL_EXPORTER_OTLP_HEADERS or "")

        # Create OTLP HTTP log exporter
        otlp_exporter = OTLPLogExporter(
            endpoint=settings.OTEL_EXPORTER_OTLP_LOGS_ENDPOINT,
            headers=headers,
        )

        # Add batch processor for efficient log export
        log_processor = BatchLogRecordProcessor(otlp_exporter)
        provider.add_log_record_processor(log_processor)

        logger.info(
            "otel_logger_provider_created",
            endpoint=settings.OTEL_EXPORTER_OTLP_LOGS_ENDPOINT,
            service_name=settings.OTEL_SERVICE_NAME,
            environment=settings.OTEL_ENVIRONMENT,
            log_level=settings.OTEL_LOG_LEVEL,
        )
    else:
        logger.warning("otel_no_logs_endpoint_configured", message="logs will not be exported to OTLP")

    return provider


def shutdown_logger_provider() -> None:
    """
    Shutdown LoggerProvider gracefully.

    Flushes any pending log records and releases resources.
    Safe to call multiple times or when provider is None.
    """
    if _logger_provider is not None:
        _logger_provider.shutdown()  # type: ignore[no-untyped-call]  # SDK method lacks type annotations
        logger.info("otel_logger_provider_shutdown")


def set_logger_provider() -> None:
    """
    Set the global LoggerProvider for OTEL log instrumentation.

    This should be called after fork (in lifespan or worker init) to ensure
    the LoggerProvider is properly initialized in each process.
    """
    if provider := get_logger_provider():
        otel_set_logger_provider(provider)


# OpenTelemetry attribute values can be primitives or lists of primitives
AttributeValue = str | int | float | bool | list[str] | list[int] | list[float] | list[bool]


@contextmanager
def service_span(
    name: str,
    service: str,
    kind: SpanKind = SpanKind.INTERNAL,
    **attributes: AttributeValue,
) -> Generator["Span"]:
    """Context manager for service operation spans with explicit status.

    Creates an OpenTelemetry span with consistent attributes and proper status handling:
    - Sets StatusCode.OK on successful completion
    - SDK automatically records exceptions and sets StatusCode.ERROR on failure

    Note: The tracer is acquired at call time (not module import time) to ensure
    it uses the TracerProvider set during application startup. This enables proper
    trace context propagation from parent spans.

    Args:
        name: Span name (e.g., "send_email", "process_alerts")
        service: Service name for peer.service attribute (e.g., "smtp", "alert-service")
        kind: Span kind (default INTERNAL, use CLIENT for external calls)
        **attributes: Additional span attributes

    Yields:
        Span: The active span for setting additional attributes

    Example:
        with service_span("send_email", "smtp", kind=SpanKind.CLIENT, recipient=email) as span:
            await send_email(...)
            span.set_attribute("smtp.message_id", message_id)
    """
    # Get tracer at call time to use the correct TracerProvider (set in lifespan/worker init)
    tracer = trace.get_tracer(__name__)
    span_attributes = {
        "peer.service": service,
        **attributes,
    }
    with tracer.start_as_current_span(
        name,
        kind=kind,
        attributes=span_attributes,
    ) as span:
        try:
            yield span
            # Set OK status on successful completion
            span.set_status(Status(StatusCode.OK))
        except Exception:
            # Let exception propagate - SDK records it and sets ERROR status
            raise


def get_current_span() -> "Span":
    """
    Get the current active span in the context.

    Utility function for adding custom attributes to the current span.

    Returns:
        Current active Span, or INVALID_SPAN (a NonRecordingSpan) if no span is active

    Note:
        Always returns a Span object (never None). When no span is active,
        returns INVALID_SPAN which is a NonRecordingSpan(INVALID_SPAN_CONTEXT).
        Check span.get_span_context().is_valid to verify there's a valid recording span.

    Example:
        >>> span = get_current_span()
        >>> if span.get_span_context().is_valid:
        ...     span.set_attribute("user.id", user_id)
    """
    return trace.get_current_span()


def get_current_trace_id() -> str | None:
    """
    Get current OpenTelemetry trace ID for correlation.

    Extracts the trace ID from the current active span context. Useful for
    correlating database records with distributed traces.

    Returns:
        32-character hex trace ID, or None if no valid span context
        (e.g., when get_current_span() returns INVALID_SPAN)

    Note:
        Returns None when there's no active span. The SDK's get_current_span()
        returns INVALID_SPAN in this case, which has an invalid context.

    Example:
        >>> trace_id = get_current_trace_id()
        >>> if trace_id:
        ...     log_entry.trace_id = trace_id
    """
    span = trace.get_current_span()
    ctx = span.get_span_context()
    # INVALID_SPAN has is_valid=False, so this check handles that case
    if not ctx.is_valid or ctx.trace_id == 0:
        return None
    return format(ctx.trace_id, "032x")
