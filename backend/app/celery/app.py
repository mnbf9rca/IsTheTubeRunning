"""Celery application instance and configuration."""

from app.core.config import require_config, settings
from app.core.logging import configure_logging
from celery import Celery

# Configure logging for Celery workers
# This ensures structlog integrates properly with Celery's logging system
configure_logging(log_level="INFO")

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

# Import tasks to register them with Celery
# This must come after celery_app is created so tasks can use the @celery_app.task decorator
from app.celery import tasks  # noqa: E402, F401
