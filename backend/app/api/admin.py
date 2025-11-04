"""Admin API endpoints for system management."""

from datetime import UTC, datetime

from celery.app.control import Inspect
from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.celery.app import celery_app
from app.core.admin import require_admin
from app.core.database import get_db
from app.models.admin import AdminUser
from app.models.notification import NotificationLog, NotificationStatus
from app.schemas.admin import (
    NotificationLogItem,
    RecentLogsResponse,
    TriggerCheckResponse,
    WorkerStatusResponse,
)
from app.schemas.tfl import BuildGraphResponse
from app.services.alert_service import AlertService, get_redis_client
from app.services.tfl_service import TfLService

router = APIRouter(prefix="/admin", tags=["admin"])


# ==================== API Endpoints ====================


@router.post("/tfl/build-graph", response_model=BuildGraphResponse)
async def build_tfl_graph(
    admin_user: AdminUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> BuildGraphResponse:
    """
    Build the station connection graph from TfL API data.

    This endpoint fetches station sequences for all tube lines and populates
    the StationConnection table with bidirectional connections. This is required
    for route validation.

    **Requires admin privileges.**

    Args:
        admin_user: Authenticated admin user
        db: Database session

    Returns:
        Build statistics (lines, stations, connections count)

    Raises:
        HTTPException: 403 if not admin, 503 if TfL API is unavailable, 500 if build fails
    """
    tfl_service = TfLService(db)

    result = await tfl_service.build_station_graph()

    return BuildGraphResponse(
        success=True,
        message="Station connection graph built successfully.",
        lines_count=result["lines_count"],
        stations_count=result["stations_count"],
        connections_count=result["connections_count"],
    )


# ==================== Alert Management Endpoints ====================


@router.post("/alerts/trigger-check", response_model=TriggerCheckResponse)
async def trigger_alert_check(
    admin_user: AdminUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> TriggerCheckResponse:
    """
    Manually trigger an immediate disruption check for all active routes.

    This endpoint bypasses the normal Celery schedule and runs the alert
    processing immediately. Useful for testing or forcing an update after
    known TfL issues.

    **Requires admin privileges.**

    Args:
        admin_user: Authenticated admin user
        db: Database session

    Returns:
        Statistics about the alert check (routes checked, alerts sent, errors)

    Raises:
        HTTPException: 403 if not admin, 500 if check fails
    """
    redis_client = await get_redis_client()
    try:
        alert_service = AlertService(db, redis_client)
        stats = await alert_service.process_all_routes()

        return TriggerCheckResponse(
            success=True,
            message=(
                f"Alert check completed: {stats['alerts_sent']} alert(s) sent to {stats['routes_checked']} route(s)."
            ),
            routes_checked=stats["routes_checked"],
            alerts_sent=stats["alerts_sent"],
            errors=stats["errors"],
        )
    finally:
        await redis_client.aclose()  # type: ignore[attr-defined]


@router.get("/alerts/worker-status", response_model=WorkerStatusResponse)
async def get_worker_status(
    admin_user: AdminUser = Depends(require_admin),
) -> WorkerStatusResponse:
    """
    Check Celery worker health and status.

    This endpoint inspects the Celery worker(s) to determine if they are
    running and processing tasks correctly.

    **Requires admin privileges.**

    Args:
        admin_user: Authenticated admin user

    Returns:
        Worker status information (availability, active tasks, scheduled tasks)

    Raises:
        HTTPException: 403 if not admin
    """
    # Use Celery inspection API to check worker status
    inspector: Inspect = celery_app.control.inspect()

    # Check active tasks
    active_tasks = inspector.active()
    active_count = sum(len(tasks) for tasks in active_tasks.values()) if active_tasks else 0

    # Check scheduled tasks
    scheduled_tasks = inspector.scheduled()
    scheduled_count = sum(len(tasks) for tasks in scheduled_tasks.values()) if scheduled_tasks else 0

    # Check if at least one worker is responding
    worker_available = active_tasks is not None

    # Try to get last heartbeat (workers send periodic stats)
    stats = inspector.stats()
    last_heartbeat = None
    if stats:
        # Workers are alive and responding
        last_heartbeat = datetime.now(UTC)

    message = "Worker is healthy and processing tasks." if worker_available else "No workers available or responding."

    return WorkerStatusResponse(
        worker_available=worker_available,
        active_tasks=active_count,
        scheduled_tasks=scheduled_count,
        last_heartbeat=last_heartbeat,
        message=message,
    )


@router.get("/alerts/recent-logs", response_model=RecentLogsResponse)
async def get_recent_notification_logs(
    admin_user: AdminUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=1000, description="Number of logs to return"),
    offset: int = Query(0, ge=0, description="Starting offset for pagination"),
    status: NotificationStatus | None = Query(None, description="Filter by notification status"),
) -> RecentLogsResponse:
    """
    Retrieve recent notification logs with pagination and filtering.

    This endpoint returns notification logs in reverse chronological order
    (most recent first) with optional status filtering.

    **Requires admin privileges.**

    Args:
        admin_user: Authenticated admin user
        db: Database session
        limit: Number of logs per page (1-1000, default 50)
        offset: Starting offset for pagination (default 0)
        status: Optional filter by notification status (sent/failed/pending)

    Returns:
        Paginated list of notification logs with total count

    Raises:
        HTTPException: 403 if not admin
    """
    # Build query with optional status filter
    query = select(NotificationLog)
    if status is not None:
        query = query.where(NotificationLog.status == status)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    result = await db.execute(count_query)
    total = result.scalar() or 0

    # Get paginated logs ordered by sent_at descending (most recent first)
    query = query.order_by(desc(NotificationLog.sent_at)).limit(limit).offset(offset)
    result = await db.execute(query)
    logs_sequence = result.scalars().all()

    # Convert to response models
    log_items: list[NotificationLogItem] = []
    for log in logs_sequence:
        log_items.append(NotificationLogItem.model_validate(log))

    return RecentLogsResponse(
        total=total,
        logs=log_items,
        limit=limit,
        offset=offset,
    )
