"""TfL API endpoints for transport data."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.tfl import (
    DisruptionResponse,
    LineResponse,
    RouteValidationRequest,
    RouteValidationResponse,
    StationResponse,
)
from app.services.tfl_service import TfLService

router = APIRouter(prefix="/tfl", tags=["tfl"])


# ==================== API Endpoints ====================


@router.get("/lines", response_model=list[LineResponse])
async def get_lines(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[LineResponse]:
    """
    Get all tube lines.

    Returns cached data from Redis or fetches from TfL API if cache expired.
    Data is cached for 24 hours (or TTL specified by TfL API).

    Args:
        current_user: Authenticated user
        db: Database session

    Returns:
        List of tube lines with metadata

    Raises:
        HTTPException: 503 if TfL API is unavailable
    """
    tfl_service = TfLService(db)
    lines = await tfl_service.fetch_lines()
    return [LineResponse.model_validate(line) for line in lines]


@router.get("/stations", response_model=list[StationResponse])
async def get_stations(
    line_id: str | None = Query(None, description="Filter stations by TfL line ID (e.g., 'victoria')"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[StationResponse]:
    """
    Get tube stations, optionally filtered by line.

    Returns cached data from Redis or fetches from TfL API if cache expired.
    Data is cached for 24 hours (or TTL specified by TfL API).

    Args:
        line_id: Optional TfL line ID to filter stations
        current_user: Authenticated user
        db: Database session

    Returns:
        List of stations with location and line information

    Raises:
        HTTPException: 503 if TfL API is unavailable
    """
    tfl_service = TfLService(db)
    stations = await tfl_service.fetch_stations(line_tfl_id=line_id)
    return [StationResponse.model_validate(station) for station in stations]


@router.get("/disruptions", response_model=list[DisruptionResponse])
async def get_disruptions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DisruptionResponse]:
    """
    Get current disruptions across the tube network.

    Returns only non-"Good Service" statuses (delays, closures, etc.).
    Data is cached for 2 minutes (or TTL specified by TfL API).

    Args:
        current_user: Authenticated user
        db: Database session

    Returns:
        List of current disruptions with severity and details

    Raises:
        HTTPException: 503 if TfL API is unavailable
    """
    tfl_service = TfLService(db)
    return await tfl_service.fetch_disruptions()


@router.post("/validate-route", response_model=RouteValidationResponse)
async def validate_route(
    request: RouteValidationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RouteValidationResponse:
    """
    Validate a multi-segment route.

    Checks if valid connections exist between consecutive stations on the
    specified lines using the station connection graph. Uses BFS for pathfinding.

    **Note**: Station connection graph must be built first using the admin
    endpoint POST /admin/tfl/build-graph.

    Args:
        request: Route segments (ordered list of station + line pairs)
        current_user: Authenticated user
        db: Database session

    Returns:
        Validation result with success status and helpful error messages

    Raises:
        HTTPException: 500 if validation fails
    """
    tfl_service = TfLService(db)
    is_valid, message, invalid_segment_index = await tfl_service.validate_route(request.segments)

    return RouteValidationResponse(
        valid=is_valid,
        message=message,
        invalid_segment_index=invalid_segment_index,
    )
