"""Routes API endpoints for managing user commute routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.route import Route, RouteSchedule, RouteSegment
from app.models.user import User
from app.schemas.routes import (
    CreateRouteRequest,
    CreateScheduleRequest,
    RouteListItemResponse,
    RouteResponse,
    ScheduleResponse,
    SegmentResponse,
    UpdateRouteRequest,
    UpdateScheduleRequest,
    UpdateSegmentRequest,
    UpsertSegmentsRequest,
)
from app.services.route_service import RouteService

router = APIRouter(prefix="/routes", tags=["routes"])


# ==================== Route Endpoints ====================


@router.get("", response_model=list[RouteListItemResponse])
async def list_routes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, str | int | None | bool]]:
    """
    List all routes for the authenticated user.

    Returns all routes (both active and inactive) with segment and schedule counts.
    The frontend can filter by active status if needed.

    Args:
        current_user: Authenticated user
        db: Database session

    Returns:
        List of routes with counts
    """
    service = RouteService(db)
    routes = await service.list_routes(current_user.id)

    # Build response with counts
    return [
        {
            "id": str(route.id),
            "name": route.name,
            "description": route.description,
            "active": route.active,
            "segment_count": len(route.segments),
            "schedule_count": len(route.schedules),
        }
        for route in routes
    ]


@router.post("", response_model=RouteResponse, status_code=status.HTTP_201_CREATED)
async def create_route(
    request: CreateRouteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Route:
    """
    Create a new route.

    Creates a route with no segments or schedules initially.
    Use the segments and schedules endpoints to add them after creation.

    Args:
        request: Route creation request
        current_user: Authenticated user
        db: Database session

    Returns:
        Created route
    """
    service = RouteService(db)
    route = await service.create_route(current_user.id, request)

    # Refresh to load empty relationships
    await db.refresh(route, ["segments", "schedules"])
    return route


@router.get("/{route_id}", response_model=RouteResponse)
async def get_route(
    route_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Route:
    """
    Get a route by ID with all segments and schedules.

    Args:
        route_id: Route UUID
        current_user: Authenticated user
        db: Database session

    Returns:
        Route with segments and schedules

    Raises:
        HTTPException: 404 if route not found or doesn't belong to user
    """
    service = RouteService(db)
    return await service.get_route_by_id(route_id, current_user.id, load_relationships=True)


@router.patch("/{route_id}", response_model=RouteResponse)
async def update_route(
    route_id: UUID,
    request: UpdateRouteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Route:
    """
    Update route metadata (name, description, active status).

    Only updates fields that are provided in the request.

    Args:
        route_id: Route UUID
        request: Update request
        current_user: Authenticated user
        db: Database session

    Returns:
        Updated route

    Raises:
        HTTPException: 404 if route not found or doesn't belong to user
    """
    service = RouteService(db)
    route = await service.update_route(route_id, current_user.id, request)

    # Refresh to load relationships
    await db.refresh(route, ["segments", "schedules"])
    return route


@router.delete("/{route_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_route(
    route_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a route.

    This also deletes all associated segments and schedules (CASCADE).

    Args:
        route_id: Route UUID
        current_user: Authenticated user
        db: Database session

    Raises:
        HTTPException: 404 if route not found or doesn't belong to user
    """
    service = RouteService(db)
    await service.delete_route(route_id, current_user.id)


# ==================== Segment Endpoints ====================


@router.put("/{route_id}/segments", response_model=list[SegmentResponse])
async def upsert_segments(
    route_id: UUID,
    request: UpsertSegmentsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RouteSegment]:
    """
    Replace all segments for a route.

    This validates the route before saving. If validation fails, no changes are made.
    Segments must be ordered with consecutive sequences starting from 0.

    Args:
        route_id: Route UUID
        request: Segments to set
        current_user: Authenticated user
        db: Database session

    Returns:
        Created segments

    Raises:
        HTTPException: 404 if route not found, 400 if validation fails
    """
    service = RouteService(db)
    return await service.upsert_segments(route_id, current_user.id, request.segments)


@router.patch("/{route_id}/segments/{sequence}", response_model=SegmentResponse)
async def update_segment(
    route_id: UUID,
    sequence: int,
    request: UpdateSegmentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RouteSegment:
    """
    Update a single segment.

    This validates the entire route after the update. If validation fails,
    the update is rolled back.

    Args:
        route_id: Route UUID
        sequence: Segment sequence number (0-based)
        request: Update request
        current_user: Authenticated user
        db: Database session

    Returns:
        Updated segment

    Raises:
        HTTPException: 404 if route or segment not found, 400 if validation fails
    """
    service = RouteService(db)
    return await service.update_segment(route_id, current_user.id, sequence, request)


@router.delete("/{route_id}/segments/{sequence}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_segment(
    route_id: UUID,
    sequence: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a segment and resequence remaining segments.

    Cannot delete if it would leave fewer than 2 segments.

    Args:
        route_id: Route UUID
        sequence: Segment sequence number (0-based)
        current_user: Authenticated user
        db: Database session

    Raises:
        HTTPException: 404 if route or segment not found, 400 if would leave <2 segments
    """
    service = RouteService(db)
    await service.delete_segment(route_id, current_user.id, sequence)


# ==================== Schedule Endpoints ====================


@router.post("/{route_id}/schedules", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    route_id: UUID,
    request: CreateScheduleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RouteSchedule:
    """
    Create a schedule for a route.

    A route can have multiple schedules (e.g., different times for weekdays vs weekends).

    Args:
        route_id: Route UUID
        request: Schedule creation request
        current_user: Authenticated user
        db: Database session

    Returns:
        Created schedule

    Raises:
        HTTPException: 404 if route not found
    """
    service = RouteService(db)
    return await service.create_schedule(route_id, current_user.id, request)


@router.patch("/{route_id}/schedules/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    route_id: UUID,
    schedule_id: UUID,
    request: UpdateScheduleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RouteSchedule:
    """
    Update a schedule.

    Only updates fields that are provided in the request.

    Args:
        route_id: Route UUID
        schedule_id: Schedule UUID
        request: Update request
        current_user: Authenticated user
        db: Database session

    Returns:
        Updated schedule

    Raises:
        HTTPException: 404 if route or schedule not found, 400 if time validation fails
    """
    service = RouteService(db)
    return await service.update_schedule(route_id, schedule_id, current_user.id, request)


@router.delete("/{route_id}/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    route_id: UUID,
    schedule_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a schedule.

    Args:
        route_id: Route UUID
        schedule_id: Schedule UUID
        current_user: Authenticated user
        db: Database session

    Raises:
        HTTPException: 404 if route or schedule not found
    """
    service = RouteService(db)
    await service.delete_schedule(route_id, schedule_id, current_user.id)
