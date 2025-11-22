"""Routes API endpoints for managing user commute routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.helpers.disruption_helpers import (
    calculate_affected_segments,
    calculate_affected_stations,
    extract_line_station_pairs,
)
from app.models.user import User
from app.models.user_route import UserRoute, UserRouteSchedule, UserRouteSegment
from app.schemas.routes import (
    CreateUserRouteRequest,
    CreateUserRouteScheduleRequest,
    RouteDisruptionResponse,
    UpdateUserRouteRequest,
    UpdateUserRouteScheduleRequest,
    UpdateUserRouteSegmentRequest,
    UpsertUserRouteSegmentsRequest,
    UserRouteListItemResponse,
    UserRouteResponse,
    UserRouteScheduleResponse,
    UserRouteSegmentResponse,
)
from app.services.disruption_matching_service import DisruptionMatchingService
from app.services.tfl_service import TfLService
from app.services.user_route_service import UserRouteService

router = APIRouter(prefix="/routes", tags=["routes"])


# ==================== Route Endpoints ====================


@router.get("", response_model=list[UserRouteListItemResponse])
async def list_routes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[UserRouteListItemResponse]:
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
    service = UserRouteService(db)
    routes = await service.list_routes(current_user.id)

    # Build response with counts using Pydantic models
    return [
        UserRouteListItemResponse(
            id=route.id,
            name=route.name,
            description=route.description,
            active=route.active,
            timezone=route.timezone,
            segment_count=len(route.segments),
            schedule_count=len(route.schedules),
        )
        for route in routes
    ]


@router.post("", response_model=UserRouteResponse, status_code=status.HTTP_201_CREATED)
async def create_route(
    request: CreateUserRouteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserRoute:
    """
    Create a new route.

    Creates a route with no segments or schedules initially.
    Use the segments and schedules endpoints to add them after creation.

    Args:
        request: UserRoute creation request
        current_user: Authenticated user
        db: Database session

    Returns:
        Created route
    """
    service = UserRouteService(db)
    route = await service.create_route(current_user.id, request)

    # Reload with full relationships for response serialization
    return await service.get_route_by_id(route.id, current_user.id, load_relationships=True)


# ==================== Disruption Endpoints ====================


@router.get("/disruptions", response_model=list[RouteDisruptionResponse])
async def get_route_disruptions(
    active_only: bool = True,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RouteDisruptionResponse]:
    """
    Get current disruptions affecting user's routes.

    Returns only disruptions affecting the authenticated user's routes.
    Uses cached TfL data (2-minute TTL) and station-level matching via
    UserRouteStationIndex for precision.

    Args:
        active_only: If True, only check active routes. If False, check all routes.
            Defaults to True.
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        List of route disruptions with affected segments and stations.
        One entry per route-disruption pair (a route may appear multiple times
        if affected by multiple disruptions).

    Raises:
        HTTPException: 503 if TfL API is unavailable
    """
    # Initialize services
    route_service = UserRouteService(db)
    matching_service = DisruptionMatchingService(db)
    tfl_service = TfLService(db)

    # 1. Fetch user's routes
    routes = await route_service.list_routes(current_user.id)

    # 2. If no routes, return empty list (check before filtering)
    if not routes:
        return []

    # 3. Filter by active_only if needed
    if active_only:
        routes = [route for route in routes if route.active]
        # Early return if no active routes (avoid unnecessary TfL API call)
        if not routes:
            return []

    # 4. Try to fetch all TfL disruptions
    try:
        all_disruptions = await tfl_service.fetch_line_disruptions(use_cache=True)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"TfL API unavailable: {e!s}",
        ) from e

    # 5. Filter disruptions to only alertable ones
    alertable_disruptions = await matching_service.filter_alertable_disruptions(all_disruptions)

    # 6. If no disruptions, return empty list
    if not alertable_disruptions:
        return []

    # 7. Match disruptions to routes
    route_disruptions: list[RouteDisruptionResponse] = []

    for route in routes:
        # Get route index pairs
        route_index_pairs = await matching_service.get_route_index_pairs(route.id)

        # Match disruptions to this route
        matched_disruptions = matching_service.match_disruptions_to_route(route_index_pairs, alertable_disruptions)

        # For each matched disruption, calculate affected segments and stations
        for disruption in matched_disruptions:
            # Extract disruption pairs for calculating affected stations
            disruption_pairs = extract_line_station_pairs(disruption)
            disruption_pairs_set = set(disruption_pairs)

            # Calculate affected segments
            # route.segments already loaded by list_routes() via selectinload
            affected_segments = calculate_affected_segments(route.segments, disruption_pairs_set)

            # Calculate affected stations
            affected_stations = calculate_affected_stations(route_index_pairs, disruption_pairs_set)

            # Build response
            route_disruptions.append(
                RouteDisruptionResponse(
                    route_id=route.id,
                    route_name=route.name,
                    disruption=disruption,
                    affected_segments=affected_segments,
                    affected_stations=affected_stations,
                )
            )

    return route_disruptions


# ==================== Route CRUD Endpoints ====================


@router.get("/{route_id}", response_model=UserRouteResponse)
async def get_route(
    route_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserRoute:
    """
    Get a route by ID with all segments and schedules.

    Args:
        route_id: UserRoute UUID
        current_user: Authenticated user
        db: Database session

    Returns:
        Route with segments and schedules

    Raises:
        HTTPException: 404 if route not found or doesn't belong to user
    """
    service = UserRouteService(db)
    return await service.get_route_by_id(route_id, current_user.id, load_relationships=True)


@router.patch("/{route_id}", response_model=UserRouteResponse)
async def update_route(
    route_id: UUID,
    request: UpdateUserRouteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserRoute:
    """
    Update route metadata (name, description, active status).

    Only updates fields that are provided in the request.

    Args:
        route_id: UserRoute UUID
        request: Update request
        current_user: Authenticated user
        db: Database session

    Returns:
        Updated route

    Raises:
        HTTPException: 404 if route not found or doesn't belong to user
    """
    service = UserRouteService(db)
    await service.update_route(route_id, current_user.id, request)

    # Reload with full relationships for response serialization
    return await service.get_route_by_id(route_id, current_user.id, load_relationships=True)


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
        route_id: UserRoute UUID
        current_user: Authenticated user
        db: Database session

    Raises:
        HTTPException: 404 if route not found or doesn't belong to user
    """
    service = UserRouteService(db)
    await service.delete_route(route_id, current_user.id)


# ==================== Segment Endpoints ====================


@router.put("/{route_id}/segments", response_model=list[UserRouteSegmentResponse])
async def upsert_segments(
    route_id: UUID,
    request: UpsertUserRouteSegmentsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[UserRouteSegment]:
    """
    Replace all segments for a route.

    This validates the route before saving. If validation fails, no changes are made.
    Segments must be ordered with consecutive sequences starting from 0.

    Args:
        route_id: UserRoute UUID
        request: Segments to set
        current_user: Authenticated user
        db: Database session

    Returns:
        Created segments

    Raises:
        HTTPException: 404 if route not found, 400 if validation fails
    """
    service = UserRouteService(db)
    return await service.upsert_segments(route_id, current_user.id, request.segments)


@router.patch("/{route_id}/segments/{sequence}", response_model=UserRouteSegmentResponse)
async def update_segment(
    route_id: UUID,
    sequence: int,
    request: UpdateUserRouteSegmentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserRouteSegment:
    """
    Update a single segment.

    This validates the entire route after the update. If validation fails,
    the update is rolled back.

    Args:
        route_id: UserRoute UUID
        sequence: Segment sequence number (0-based)
        request: Update request
        current_user: Authenticated user
        db: Database session

    Returns:
        Updated segment

    Raises:
        HTTPException: 404 if route or segment not found, 400 if validation fails
    """
    service = UserRouteService(db)
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
        route_id: UserRoute UUID
        sequence: Segment sequence number (0-based)
        current_user: Authenticated user
        db: Database session

    Raises:
        HTTPException: 404 if route or segment not found, 400 if would leave <2 segments
    """
    service = UserRouteService(db)
    await service.delete_segment(route_id, current_user.id, sequence)


# ==================== Schedule Endpoints ====================


@router.post("/{route_id}/schedules", response_model=UserRouteScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    route_id: UUID,
    request: CreateUserRouteScheduleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserRouteSchedule:
    """
    Create a schedule for a route.

    A route can have multiple schedules (e.g., different times for weekdays vs weekends).

    Args:
        route_id: UserRoute UUID
        request: Schedule creation request
        current_user: Authenticated user
        db: Database session

    Returns:
        Created schedule

    Raises:
        HTTPException: 404 if route not found
    """
    service = UserRouteService(db)
    return await service.create_schedule(route_id, current_user.id, request)


@router.patch("/{route_id}/schedules/{schedule_id}", response_model=UserRouteScheduleResponse)
async def update_schedule(
    route_id: UUID,
    schedule_id: UUID,
    request: UpdateUserRouteScheduleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserRouteSchedule:
    """
    Update a schedule.

    Only updates fields that are provided in the request.

    Args:
        route_id: UserRoute UUID
        schedule_id: Schedule UUID
        request: Update request
        current_user: Authenticated user
        db: Database session

    Returns:
        Updated schedule

    Raises:
        HTTPException: 404 if route or schedule not found, 400 if time validation fails
    """
    service = UserRouteService(db)
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
        route_id: UserRoute UUID
        schedule_id: Schedule UUID
        current_user: Authenticated user
        db: Database session

    Raises:
        HTTPException: 404 if route or schedule not found
    """
    service = UserRouteService(db)
    await service.delete_schedule(route_id, schedule_id, current_user.id)
