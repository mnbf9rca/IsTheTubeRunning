"""Celery tasks for background processing.

This module defines all Celery tasks for the application, including the main
periodic task that checks for TfL disruptions and sends alerts to users.
"""

import asyncio
from typing import Protocol, TypedDict
from uuid import UUID

import structlog
from sqlalchemy import select

from app.celery.app import celery_app
from app.celery.database import worker_session_factory
from app.models.route import Route
from app.services.alert_service import AlertService, get_redis_client
from app.services.route_index_service import RouteIndexService

logger = structlog.get_logger(__name__)


# Protocol for Celery task request
class TaskRequest(Protocol):
    """Protocol for Celery task request object."""

    @property
    def retries(self) -> int:
        """Number of times task has been retried."""
        ...


# Protocol for Celery bound task
class BoundTask(Protocol):
    """Protocol for Celery bound task self parameter."""

    @property
    def request(self) -> TaskRequest:
        """Task request object."""
        ...

    def retry(self, exc: Exception | None = None, countdown: int | None = None) -> Exception:
        """
        Retry the task.

        This method raises an exception to signal task retry.
        """
        ...


# Type definitions for task return values
class DisruptionCheckResult(TypedDict):
    """Result from check_disruptions_and_alert task."""

    status: str
    routes_checked: int
    alerts_sent: int
    errors: int


class RebuildIndexesResult(TypedDict):
    """Result from rebuild_route_indexes task."""

    status: str
    rebuilt_count: int
    failed_count: int
    errors: list[str]


@celery_app.task(  # type: ignore[arg-type]
    bind=True,
    max_retries=3,
    name="app.celery.tasks.check_disruptions_and_alert",
)
def check_disruptions_and_alert(self: BoundTask) -> DisruptionCheckResult:
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
        DisruptionCheckResult: Task execution result with status and statistics

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


async def _check_disruptions_async() -> DisruptionCheckResult:
    """
    Async implementation of disruption checking logic.

    This function contains all the async database and API operations needed
    to check for disruptions and send alerts. It properly manages the database
    session lifecycle and Redis connection.

    Returns:
        DisruptionCheckResult: Execution statistics including routes_checked, alerts_sent, and errors
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

        return DisruptionCheckResult(
            status="success",
            routes_checked=result["routes_checked"],
            alerts_sent=result["alerts_sent"],
            errors=result["errors"],
        )

    finally:
        # Ensure resources are properly closed
        if redis_client is not None:
            await redis_client.aclose()
        if session is not None:
            await session.close()


@celery_app.task(  # type: ignore[arg-type]
    bind=True,
    max_retries=3,
    name="app.celery.tasks.rebuild_route_indexes",
)
def rebuild_route_indexes_task(
    self: BoundTask,
    route_id: str | None = None,
) -> RebuildIndexesResult:
    """
    Rebuild route station indexes for single route or all routes.

    This task can be triggered manually via admin API or scheduled for maintenance.
    It rebuilds the inverted index that maps (line_tfl_id, station_naptan) → route_id.

    Args:
        self: Celery task instance (bound via bind=True)
        route_id: Optional route UUID string. If provided, rebuilds only that route.
                  If None, rebuilds all routes.

    Returns:
        RebuildIndexesResult: Task execution result with rebuilt_count, failed_count, and errors

    Raises:
        Retry: If the task should be retried due to transient failure
    """
    try:
        # Run async logic in the event loop
        result = asyncio.run(_rebuild_indexes_async(route_id))
        logger.info(
            "rebuild_indexes_task_completed",
            route_id=route_id,
            result=result,
        )
        return result

    except Exception as exc:
        logger.error(
            "rebuild_indexes_task_failed",
            route_id=route_id,
            error=str(exc),
            error_type=type(exc).__name__,
            retry_count=self.request.retries,
        )
        # Retry with exponential backoff (60s countdown)
        raise self.retry(exc=exc, countdown=60) from exc


async def _rebuild_indexes_async(route_id_str: str | None = None) -> RebuildIndexesResult:
    """
    Async implementation of route index rebuilding logic.

    Args:
        route_id_str: Optional route UUID as string

    Returns:
        RebuildIndexesResult: Execution statistics including rebuilt_count, failed_count, and errors
    """
    session = None
    try:
        # Create database session for this task
        session = worker_session_factory()
        index_service = RouteIndexService(session)

        rebuilt_count = 0
        failed_count = 0
        errors: list[str] = []

        if route_id_str:
            # Rebuild single route
            route_id = UUID(route_id_str)
            try:
                await index_service.build_route_station_index(route_id, auto_commit=True)
                rebuilt_count = 1
            except Exception as exc:
                failed_count = 1
                errors.append(f"Route {route_id}: {exc!s}")
        else:
            # Rebuild all routes
            result = await session.execute(select(Route))
            routes = result.scalars().all()

            for route in routes:
                try:
                    await index_service.build_route_station_index(route.id, auto_commit=True)
                    rebuilt_count += 1
                except Exception as exc:
                    failed_count += 1
                    errors.append(f"Route {route.id}: {exc!s}")

        return RebuildIndexesResult(
            status="success" if failed_count == 0 else "partial_failure",
            rebuilt_count=rebuilt_count,
            failed_count=failed_count,
            errors=errors,
        )

    finally:
        # Ensure resources are properly closed
        if session is not None:
            await session.close()
