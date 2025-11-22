"""Celery application instance and configuration."""

import structlog
from celery.signals import beat_init, worker_ready
from opentelemetry import trace

from app.core.config import require_config, settings
from app.core.logging import configure_logging
from celery import Celery

logger = structlog.get_logger(__name__)

# Configure logging for Celery workers
# This ensures structlog integrates properly with Celery's logging system
configure_logging(log_level=settings.LOG_LEVEL)

# Validate required Celery configuration
require_config("CELERY_BROKER_URL", "CELERY_RESULT_BACKEND")

# Create Celery application instance
celery_app = Celery("isthetuberunning")

# Configure Celery
celery_app.conf.update(
    # Redis Configuration
    # Use separate Redis databases for broker (1) and results (2) to avoid key conflicts
    broker_url=settings.CELERY_BROKER_URL,
    result_backend=settings.CELERY_RESULT_BACKEND,
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Task tracking
    task_track_started=True,
    # Task time limits (5 min hard, 4 min soft)
    task_time_limit=300,  # 5 minutes hard limit
    task_soft_time_limit=240,  # 4 minutes soft limit (raises SoftTimeLimitExceeded)
    # Logging
    # Don't hijack root logger - let structlog handle it
    worker_hijack_root_logger=False,
)

# OpenTelemetry Instrumentation
# CeleryInstrumentor wraps task execution to create spans and propagate trace context.
# The TracerProvider is set in worker_process_init (database.py) after fork for fork-safety.
# This must be called after celery_app creation but before task registration.
if settings.OTEL_ENABLED:
    from opentelemetry.instrumentation.celery import CeleryInstrumentor

    CeleryInstrumentor().instrument()
    logger.info("celery_otel_instrumentation_enabled")


@beat_init.connect
def init_beat_otel(
    **kwargs: object,
) -> None:
    """
    Initialize OpenTelemetry for Celery Beat scheduler process.

    This is called when the Beat scheduler process starts. It initializes
    the TracerProvider and LoggerProvider for the Beat process, enabling
    distributed tracing and log export for scheduled task triggers.

    Note: CeleryInstrumentor is already applied at module level above,
    this just ensures the Beat process has its own providers.
    """
    if settings.OTEL_ENABLED:
        try:
            from app.core.telemetry import (  # noqa: PLC0415  # Lazy import for fork-safety
                get_tracer_provider,
                set_logger_provider,
            )

            if provider := get_tracer_provider():
                trace.set_tracer_provider(provider)
                logger.info("beat_otel_tracer_provider_initialized")

            # Initialize LoggerProvider for log export
            set_logger_provider()
            logger.info("beat_otel_logger_provider_initialized")
        except Exception:
            logger.exception("beat_otel_initialization_failed")
            # Continue without OTEL - graceful degradation


@worker_ready.connect
def trigger_startup_tasks(
    **kwargs: object,
) -> None:
    """
    Trigger initial data population tasks when Celery worker starts.

    This ensures metadata and graph data are populated immediately on deployment
    with empty database, rather than waiting 24 hours for first scheduled run.

    The tasks use INSERT ... ON CONFLICT DO UPDATE, so if data already exists
    (populated by FastAPI startup cache warmup or manual admin API calls),
    this is a no-op that just validates the data.

    Handles race condition with FastAPI startup gracefully - both paths are idempotent.
    """
    try:
        # Trigger metadata refresh immediately
        # This populates severity_codes, disruption_categories, stop_types tables
        celery_app.send_task("app.celery.tasks.refresh_tfl_metadata")
        logger.info("worker_startup_metadata_refresh_triggered")

        # Trigger network graph rebuild immediately
        # This populates lines, stations, connections tables
        # Re-enabled after fixing #230 - now uses soft delete to eliminate 503 window
        celery_app.send_task("app.celery.tasks.rebuild_network_graph")
        logger.info("worker_startup_graph_rebuild_triggered")

    except Exception:
        logger.exception("worker_startup_tasks_failed")
        # Continue without blocking worker startup - tasks will run on schedule


# Import tasks to register them with Celery
# This must come after celery_app is created so tasks can use the @celery_app.task decorator
# Import schedules to configure Celery Beat
# CRITICAL: This import must remain - it populates celery_app.conf.beat_schedule
# Removing this import will break all periodic tasks (Issue #167)
from app.celery import (  # noqa: E402
    schedules,  # noqa: F401
    tasks,  # noqa: F401
)
