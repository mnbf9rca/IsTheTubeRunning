"""OpenTelemetry distributed tracing configuration."""

import logging
import threading
from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app import __version__
from app.core.config import require_config, settings

if TYPE_CHECKING:
    from opentelemetry.trace.span import Span

logger = logging.getLogger(__name__)

# Module-level globals for lazy initialization (fork-safety pattern from ADR 08)
_tracer_provider: TracerProvider | None = None
_tracer_provider_lock = threading.Lock()


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
    # Production mode requires OTLP endpoint
    if not settings.DEBUG:
        require_config("OTEL_EXPORTER_OTLP_ENDPOINT")

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

    # Add OTLP exporter if endpoint is configured
    if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        # Parse OTLP headers (format: "key1=value1,key2=value2")
        headers = _parse_otlp_headers(settings.OTEL_EXPORTER_OTLP_HEADERS or "")

        # Create OTLP HTTP exporter
        otlp_exporter = OTLPSpanExporter(
            endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
            headers=headers,
        )

        # Add batch processor for efficient span export
        span_processor = BatchSpanProcessor(otlp_exporter)
        provider.add_span_processor(span_processor)

        logger.info(
            f"OTEL TracerProvider created with OTLP exporter: {settings.OTEL_EXPORTER_OTLP_ENDPOINT}",
            extra={
                "service_name": settings.OTEL_SERVICE_NAME,
                "environment": settings.OTEL_ENVIRONMENT,
            },
        )
    else:
        logger.warning("OTEL enabled but no OTLP endpoint configured - traces will not be exported")

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
            logger.warning(f"Malformed OTLP header pair ignored: '{pair}'")

    return headers


def shutdown_tracer_provider() -> None:
    """
    Shutdown TracerProvider gracefully.

    Flushes any pending spans and releases resources.
    Safe to call multiple times or when provider is None.
    """
    if _tracer_provider is not None:
        _tracer_provider.shutdown()
        logger.info("OTEL TracerProvider shutdown complete")


def get_current_span() -> "Span | None":
    """
    Get the current active span in the context.

    Utility function for adding custom attributes to the current span.

    Returns:
        Current active Span or None if no span is active

    Example:
        >>> span = get_current_span()
        >>> if span:
        ...     span.set_attribute("user.id", user_id)
    """
    return trace.get_current_span()
