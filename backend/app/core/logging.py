"""Logging configuration for the application.

Configures structlog to integrate with Python's logging module so that:
- Logs have correct log levels (not all WARNING)
- Celery workers properly capture and display task logs
- Third-party library logs are formatted consistently
- Structured logging works consistently across API and worker processes
"""

import logging
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog
from opentelemetry import trace


def _add_otel_context(
    logger: logging.Logger, method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Add OpenTelemetry trace and span IDs to log events for correlation."""
    span = trace.get_current_span()
    if span and span.is_recording():
        ctx = span.get_span_context()
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict


def configure_logging(*, log_level: str = "INFO") -> None:
    """
    Configure structlog to integrate with Python's logging module.

    This ensures:
    - Structlog logs use proper log levels (info, warning, error, etc.)
    - Third-party library logs (aiocache, urllib3, Celery) go through structlog
    - Celery workers correctly capture task logs at the right level
    - Logs are output to stdout with consistent formatting

    Args:
        log_level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    normalized_level = log_level.upper()

    # Shared processors for both structlog and stdlib logs
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        _add_otel_context,  # Add trace_id/span_id from OpenTelemetry
    ]

    # Configure structlog
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Choose renderer based on log level
    if normalized_level == "DEBUG":
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    # Formatter that processes stdlib logs through structlog
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    # Configure root logger handler with structlog formatter
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, normalized_level))

    # Silence noisy third-party loggers (reduce to WARNING level)
    # These produce verbose INFO/DEBUG logs that clutter output
    noisy_loggers = [
        "aiocache",  # Redis GET/SET operations
        "urllib3",  # HTTP connection logs
        "urllib3.connectionpool",  # HTTPS connection details
        "requests",  # HTTP request logs
        "celery.app.trace",  # Task success/failure messages
        "opentelemetry.instrumentation.celery",  # OTEL signal handlers
        "opentelemetry.exporter.otlp.proto.http",  # OTLP export logs
        "uvicorn.access",  # Replaced by AccessLoggingMiddleware
    ]
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
