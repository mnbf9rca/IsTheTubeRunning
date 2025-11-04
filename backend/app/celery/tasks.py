"""Celery tasks for background processing.

This module defines all Celery tasks for the application, including the main
periodic task that checks for TfL disruptions and sends alerts to users.
"""

import asyncio
from typing import Any

import structlog

from app.celery.app import celery_app
from app.celery.database import worker_session_factory
from app.services.alert_service import AlertService, get_redis_client
from celery import Task

logger = structlog.get_logger(__name__)


@celery_app.task(
    bind=True,
    max_retries=3,
    name="app.celery.tasks.check_disruptions_and_alert",
)
def check_disruptions_and_alert(self: Task[Any]) -> dict[str, Any]:  # type: ignore[type-arg]
    """
    Check for TfL disruptions and send alerts to users with matching preferences.

    This task runs periodically via Celery Beat (every 30 seconds) and:
    1. Fetches current TfL line status
    2. Identifies users with notification preferences for disrupted lines
    3. Sends alerts via their preferred channels (email/SMS)
    4. Records alert history to prevent duplicate notifications

    The task uses async database operations and includes retry logic for
    transient failures.

    Args:
        self: Celery task instance (bound via bind=True)

    Returns:
        dict: Task execution result with status and statistics

    Raises:
        Retry: If the task should be retried due to transient failure
    """
    try:
        # Run async logic in the event loop
        result = asyncio.run(_check_disruptions_async())
        logger.info(
            "check_disruptions_task_completed",
            result=result,
        )
        return result

    except Exception as exc:
        logger.error(
            "check_disruptions_task_failed",
            error=str(exc),
            error_type=type(exc).__name__,
            retry_count=self.request.retries,
        )
        # Retry with exponential backoff (60s countdown)
        raise self.retry(exc=exc, countdown=60) from exc


async def _check_disruptions_async() -> dict[str, Any]:
    """
    Async implementation of disruption checking logic.

    This function contains all the async database and API operations needed
    to check for disruptions and send alerts. It properly manages the database
    session lifecycle and Redis connection.

    Returns:
        dict: Execution statistics including routes_checked, alerts_sent, and errors
    """
    session = None
    redis_client = None
    try:
        # Create database session and Redis client for this task
        session = worker_session_factory()
        redis_client = await get_redis_client()

        # Create AlertService instance and process all routes
        alert_service = AlertService(db=session, redis_client=redis_client)
        result = await alert_service.process_all_routes()

        return {
            "status": "success",
            **result,
        }

    finally:
        # Ensure resources are properly closed
        if redis_client is not None:
            await redis_client.close()
        if session is not None:
            await session.close()
