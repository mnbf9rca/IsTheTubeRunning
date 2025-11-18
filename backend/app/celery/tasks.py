"""Celery tasks for background processing.

This module defines all Celery tasks for the application, including the main
periodic task that checks for TfL disruptions and sends alerts to users.
"""

from collections.abc import Awaitable, Callable
from typing import Any, Protocol, TypedDict
from uuid import UUID

import structlog
from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.celery.app import celery_app
from app.celery.database import get_worker_loop, get_worker_redis_client, get_worker_session
from app.models.tfl import Line
from app.models.user_route_index import UserRouteStationIndex
from app.services.alert_service import AlertService
from app.services.user_route_index_service import UserRouteIndexService

logger = structlog.get_logger(__name__)


def run_in_worker_loop[T](
    coro_func: Callable[..., Awaitable[T]],
    *args: Any,  # noqa: ANN401 - Pass-through args to async function
    **kwargs: Any,  # noqa: ANN401 - Pass-through kwargs to async function
) -> T:
    """
    Run an async function in the worker's persistent event loop.

    This function uses the event loop created during worker initialization
    (in worker_process_init signal handler) rather than creating a new loop
    per task. This allows database connections and Redis clients to be
    properly pooled and reused across tasks.

    Args:
        coro_func: An async function (not coroutine) to execute
        *args: Positional arguments to pass to the async function
        **kwargs: Keyword arguments to pass to the async function

    Returns:
        The return value of the async function

    Raises:
        RuntimeError: If worker not initialized or event loop is closed
    """
    loop = get_worker_loop()  # Get worker's persistent loop (with guards)
    coro = coro_func(*args, **kwargs)
    return loop.run_until_complete(coro)


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


class DetectStaleRoutesResult(TypedDict):
    """Result from detect_and_rebuild_stale_routes task."""

    status: str
    stale_count: int
    triggered_count: int
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
        # run_in_worker_loop() uses the worker's persistent event loop.
        # This allows database and Redis connections to be pooled and
        # reused across tasks in the same worker process.
        result = run_in_worker_loop(_check_disruptions_async)
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
    session lifecycle. The Redis client is shared across tasks via get_worker_redis_client().

    Returns:
        DisruptionCheckResult: Execution statistics including routes_checked, alerts_sent, and errors
    """
    session = None
    try:
        # Get database session and shared Redis client
        session = get_worker_session()
        redis_client = get_worker_redis_client()

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
        # run_in_worker_loop() uses the worker's persistent event loop.
        # This allows database connections to be pooled and reused
        # across tasks in the same worker process.
        result = run_in_worker_loop(_rebuild_indexes_async, route_id)
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
        session = get_worker_session()
        index_service = UserRouteIndexService(session)

        # Parse route_id if provided
        route_id = UUID(route_id_str) if route_id_str else None

        # Use shared rebuild_routes method for consistent behavior
        result = await index_service.rebuild_routes(route_id, auto_commit=True)

        return RebuildIndexesResult(
            status="success" if result["failed_count"] == 0 else "partial_failure",
            rebuilt_count=result["rebuilt_count"],
            failed_count=result["failed_count"],
            errors=result["errors"],
        )

    finally:
        # Ensure resources are properly closed
        if session is not None:
            await session.close()


# Pure helper functions for staleness detection


async def find_stale_route_ids(session: AsyncSession) -> list[UUID]:
    """
    Find routes with stale index entries (where line data has been updated).

    This is a pure query function that identifies routes whose station indexes
    are out of date compared to the TfL line data they reference.

    Args:
        session: Database session

    Returns:
        List of route UUIDs with stale indexes (distinct, no duplicates)

    Algorithm:
        1. Join UserRouteStationIndex → Line (directly via line_tfl_id)
        2. Filter: WHERE line_data_version < Line.last_updated
        3. Return distinct route_ids (a route may have multiple stale entries)
    """
    # Query for routes where index is stale
    # Use DISTINCT because a route can have multiple index entries on the same line
    # Example: Route with 5 stations on Piccadilly → 5 index entries → could match 5 times
    # Join directly to Line using line_tfl_id (not through RouteSegment which may have NULL line_id)
    stmt = (
        select(distinct(UserRouteStationIndex.route_id))
        .join(Line, Line.tfl_id == UserRouteStationIndex.line_tfl_id)
        .where(UserRouteStationIndex.line_data_version < Line.last_updated)
    )

    result = await session.execute(stmt)
    return [row[0] for row in result.all()]


@celery_app.task(  # type: ignore[arg-type]
    bind=True,
    max_retries=3,
    name="app.celery.tasks.detect_and_rebuild_stale_routes",
)
def detect_and_rebuild_stale_routes(self: BoundTask) -> DetectStaleRoutesResult:
    """
    Detect routes with stale indexes and trigger rebuild tasks.

    This task is event-driven and triggered after TfL graph builds, typically via
    the `/admin/tfl/build-graph` endpoint. It ensures route station indexes stay
    accurate as TfL line data changes over time. When Line.route_variants JSON is
    updated, the indexes built from that data become stale.

    Algorithm:
        1. Query routes where line_data_version < Line.last_updated
        2. For each stale route, trigger rebuild_route_indexes_task.delay()
        3. Return statistics for monitoring

    Execution Strategy:
        - Triggers individual rebuild tasks for better parallelization
        - Each rebuild is isolated (one failure doesn't affect others)
        - Leverages existing tested rebuild infrastructure

    Args:
        self: Celery task instance (bound via bind=True)

    Returns:
        DetectStaleRoutesResult: Execution statistics including stale_count,
                                  triggered_count, and any errors

    Raises:
        Retry: If the task should be retried due to transient failure
    """
    try:
        # run_in_worker_loop() uses the worker's persistent event loop.
        # This allows database connections to be pooled and reused
        # across tasks in the same worker process.
        result = run_in_worker_loop(_detect_stale_routes_async)
        logger.info(
            "detect_stale_routes_task_completed",
            result=result,
        )
        return result

    except Exception as exc:
        logger.error(
            "detect_stale_routes_task_failed",
            error=str(exc),
            error_type=type(exc).__name__,
            retry_count=self.request.retries,
        )
        # Retry with exponential backoff (60s countdown)
        raise self.retry(exc=exc, countdown=60) from exc


async def _detect_stale_routes_async() -> DetectStaleRoutesResult:
    """
    Async implementation of staleness detection logic.

    This function:
        1. Queries for stale route_ids using the pure helper function
        2. Triggers individual rebuild tasks for each stale route
        3. Collects statistics for monitoring

    Returns:
        DetectStaleRoutesResult: Execution statistics including:
            - stale_count: Number of stale routes found
            - triggered_count: Number of rebuild tasks successfully triggered
            - errors: List of any errors encountered
    """
    session = None
    errors: list[str] = []
    triggered_count = 0

    try:
        # Create database session for this task
        session = get_worker_session()

        # Use pure helper function to find stale routes
        logger.info("detect_stale_routes_started")
        stale_route_ids = await find_stale_route_ids(session)
        logger.info("stale_routes_found", count=len(stale_route_ids))

        # Trigger individual rebuild task for each stale route
        # This provides better parallelization and fault isolation
        for route_id in stale_route_ids:
            try:
                rebuild_route_indexes_task.delay(str(route_id))
                triggered_count += 1
                logger.debug(
                    "rebuild_task_triggered",
                    route_id=str(route_id),
                )
            except Exception as exc:
                error_msg = f"Failed to trigger rebuild for route {route_id}: {exc}"
                logger.warning(
                    "rebuild_trigger_failed",
                    route_id=str(route_id),
                    error=str(exc),
                )
                errors.append(error_msg)

        # Determine overall status
        if triggered_count == len(stale_route_ids):
            status = "success"
        elif triggered_count == 0 and len(stale_route_ids) > 0:
            status = "failure"
        else:
            status = "partial_failure"

        return DetectStaleRoutesResult(
            status=status,
            stale_count=len(stale_route_ids),
            triggered_count=triggered_count,
            errors=errors,
        )

    finally:
        # Ensure resources are properly closed
        if session is not None:
            await session.close()
