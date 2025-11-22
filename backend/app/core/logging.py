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
from typing import TYPE_CHECKING, Any, ClassVar

import structlog
from opentelemetry import trace

if TYPE_CHECKING:
    from opentelemetry.util.types import Attributes


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


class AttrFilteredLoggingHandler:
    """LoggingHandler that removes non-serializable attributes from log records.

    Custom LoggingHandler that filters non-serializable attributes before export.
    See: https://github.com/open-telemetry/opentelemetry-python/issues/3649

    OTEL's LoggingHandler doesn't call formatters/processors, so structlog's
    _logger attribute never gets removed. This class overrides _get_attributes()
    to filter out problematic attributes before they reach the OTLP exporter.

    Note:
        This class is defined at module level to enable importability and testability,
        but is only instantiated when OTEL is enabled in configure_logging().
    """

    # Attributes to drop (structlog adds _logger, websockets adds websocket, etc.)
    DROP_ATTRIBUTES: ClassVar[list[str]] = ["_logger", "websocket"]

    def __new__(cls, *args: Any, **kwargs: Any) -> Any:  # noqa: ANN401  # Runtime class creation requires Any
        """Create instance by inheriting from LoggingHandler at runtime."""
        # Import LoggingHandler only when instantiating (lazy import for OTEL dependency)
        from opentelemetry.sdk._logs import LoggingHandler  # noqa: PLC0415

        # Create a new class that inherits from LoggingHandler
        runtime_class = type(
            "AttrFilteredLoggingHandler",
            (LoggingHandler,),
            {
                "DROP_ATTRIBUTES": cls.DROP_ATTRIBUTES,
                "_get_attributes": staticmethod(cls._get_attributes),
            },
        )
        # Return instance of the runtime class (LoggingHandler subclass)
        return runtime_class(*args, **kwargs)

    @staticmethod
    def _get_attributes(record: logging.LogRecord) -> "Attributes":
        """Extract attributes from log record, filtering non-serializable ones."""
        from opentelemetry.sdk._logs import LoggingHandler  # noqa: PLC0415

        attributes = LoggingHandler._get_attributes(record)
        if attributes is None:
            return None
        # Convert immutable Mapping to mutable dict to allow deletion
        attributes_dict = dict(attributes)
        for attr in AttrFilteredLoggingHandler.DROP_ATTRIBUTES:
            attributes_dict.pop(attr, None)
        return attributes_dict  # type: ignore[return-value]


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

    # Add OTLP log exporter if enabled
    # Lazy import to avoid circular dependency (telemetry imports logging for logger)
    from app.core.config import settings  # noqa: PLC0415

    if settings.OTEL_ENABLED:
        # Import OTEL logging components only when needed
        from app.core.telemetry import get_logger_provider  # noqa: PLC0415

        if logger_provider := get_logger_provider():
            # Determine log level for OTLP export
            otel_log_level = getattr(logging, settings.OTEL_LOG_LEVEL)

            # Create handler that exports logs to OTLP (using module-level class)
            # Note: AttrFilteredLoggingHandler returns LoggingHandler subclass instance
            otel_handler = AttrFilteredLoggingHandler(level=otel_log_level, logger_provider=logger_provider)
            root_logger.addHandler(otel_handler)  # type: ignore[arg-type]  # Runtime subclass of LoggingHandler

            # Use structlog to log this (since we're in configuration phase)
            logger = structlog.get_logger(__name__)
            logger.info(
                "otel_logging_handler_attached",
                level=settings.OTEL_LOG_LEVEL,
                endpoint=settings.OTEL_EXPORTER_OTLP_LOGS_ENDPOINT,
            )

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
