"""Logging configuration for the application.

Configures structlog to integrate with Python's logging module so that:
- Logs have correct log levels (not all WARNING)
- Celery workers properly capture and display task logs
- Structured logging works consistently across API and worker processes
"""

import logging
import sys

import structlog


def configure_logging(*, log_level: str = "INFO") -> None:
    """
    Configure structlog to integrate with Python's logging module.

    This ensures:
    - Structlog logs use proper log levels (info, warning, error, etc.)
    - Celery workers correctly capture task logs at the right level
    - Logs are output to stdout with consistent formatting

    Args:
        log_level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Configure Python's logging module
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )

    # Configure structlog to use Python's logging
    structlog.configure(
        processors=[
            # Add log level to event dict
            structlog.stdlib.add_log_level,
            # Add logger name
            structlog.stdlib.add_logger_name,
            # Add timestamp
            structlog.processors.TimeStamper(fmt="iso"),
            # Stack info for exceptions
            structlog.processors.StackInfoRenderer(),
            # Format exceptions
            structlog.processors.format_exc_info,
            # Render as JSON or key-value depending on environment
            structlog.processors.JSONRenderer() if log_level.upper() == "DEBUG" else structlog.dev.ConsoleRenderer(),
        ],
        # Use LoggerFactory for stdlib integration
        logger_factory=structlog.stdlib.LoggerFactory(),
        # Use BoundLogger for stdlib integration
        wrapper_class=structlog.stdlib.BoundLogger,
        # Cache logger instances for performance
        cache_logger_on_first_use=True,
    )
