"""API endpoints for Transport for London transport data.

These endpoints expose TfL data to our frontend, fetching from Transport for London's
official API via the pydantic-tfl-api library and our internal TfL service layer.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.tfl import (
    AlertConfigResponse,
    DisruptionCategoryResponse,
    GroupedLineDisruptionResponse,
    LineResponse,
    LineRoutesResponse,
    LineStateResponse,
    RouteValidationRequest,
    RouteValidationResponse,
    SeverityCodeResponse,
    StationDisruptionResponse,
    StationResponse,
    StationRoutesResponse,
    StopTypeResponse,
)
from app.services.tfl_service import TfLService
from app.types.tfl_api import NetworkConnection

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
    deduplicated: bool = Query(
        False,
        description=(
            "Group hub stations into single entries with aggregated lines "
            "(e.g., 'Seven Sisters' instead of separate Rail and Tube stations)"
        ),
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[StationResponse]:
    """
    Get tube stations, optionally filtered by line and/or deduplicated by hub.

    Returns cached data from Redis or database. Data is cached for 24 hours.
    Stations are populated by the admin-controlled /admin/tfl/build-graph endpoint.

    When deduplicated=true, stations that share a hub_naptan_code are grouped into
    a single representative station with:
    - tfl_id: hub NaPTAN code (e.g., 'HUBSVS' instead of '940GZZLUSVS')
    - name: hub common name (e.g., 'Seven Sisters')
    - lines: aggregated from all hub child stations

    Args:
        line_id: Optional TfL line ID to filter stations
        deduplicated: Whether to group hub stations into single entries (default: False)
        current_user: Authenticated user
        db: Database session

    Returns:
        List of stations with location and line information

    Raises:
        HTTPException: 503 if TfL data not initialized (run /admin/tfl/build-graph)
        HTTPException: 404 if line_id provided but line doesn't exist
        HTTPException: 404 if line exists but no stations found

    Examples:
        GET /tfl/stations  # All stations including hub children
        GET /tfl/stations?line_id=victoria  # Victoria line stations only
        GET /tfl/stations?deduplicated=true  # Hub-grouped stations
        GET /tfl/stations?line_id=victoria&deduplicated=true  # Victoria line, hub-grouped
    """
    tfl_service = TfLService(db)

    # When deduplicating, fetch ALL stations first to get complete hub data,
    # then filter by line after deduplication. This ensures hub representatives
    # show all lines served by the hub, not just the filtered line.
    if deduplicated:
        # Fetch all stations to get complete hub information
        stations = await tfl_service.fetch_stations(line_tfl_id=None)
        # Deduplicate to create hub representatives with all lines
        # Pass line_id so hub representatives use UUID from the line-matched station
        stations = tfl_service.deduplicate_stations_by_hub(stations, line_filter=line_id)
        # Then filter by line if requested (keeps only stations serving that line)
        if line_id:
            stations = [s for s in stations if line_id in s.lines]
    else:
        # Normal behavior: filter by line directly
        stations = await tfl_service.fetch_stations(line_tfl_id=line_id)

    return [StationResponse.model_validate(station) for station in stations]


@router.get("/disruptions", response_model=list[GroupedLineDisruptionResponse])
async def get_disruptions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[GroupedLineDisruptionResponse]:
    """
    Get current line-level disruptions across the tube network (grouped by line).

    Returns disruptions grouped by line, with multiple statuses per line combined.
    Each line appears once with all its statuses sorted by severity (lower = more severe).
    Data is cached for 2 minutes (or TTL specified by TfL API).

    Args:
        current_user: Authenticated user
        db: Database session

    Returns:
        List of grouped line disruptions (one per line) with all statuses and details

    Raises:
        HTTPException: 503 if TfL API is unavailable
    """
    tfl_service = TfLService(db)
    return await tfl_service.fetch_grouped_line_disruptions()


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


@router.get("/network-graph", response_model=dict[str, list[NetworkConnection]])
async def get_network_graph(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, list[NetworkConnection]]:
    """
    Get the station network graph as an adjacency list.

    This returns a mapping of station TfL IDs to their connected stations,
    which helps the frontend constrain user choices to valid next stations
    when building routes.

    **Note**: Station connection graph must be built first using the admin
    endpoint POST /admin/tfl/build-graph.

    Returns:
        Dictionary mapping station_tfl_id to list of connected stations with line info:
        ```json
        {
            "940GZZLUOXC": [
                {
                    "station_id": "uuid",
                    "station_tfl_id": "940GZZLUBND",
                    "station_name": "Bond Street",
                    "line_id": "uuid",
                    "line_tfl_id": "central",
                    "line_name": "Central"
                },
                ...
            ]
        }
        ```

    Args:
        current_user: Authenticated user
        db: Database session

    Raises:
        HTTPException: 503 if graph hasn't been built yet, 500 if fetch fails
    """
    tfl_service = TfLService(db)
    return await tfl_service.get_network_graph()


@router.get("/station-disruptions", response_model=list[StationDisruptionResponse])
async def get_station_disruptions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[StationDisruptionResponse]:
    """
    Get current station-level disruptions across the tube network.

    Returns disruptions affecting specific stations (e.g., station closures,
    lift outages, etc.) as opposed to line-wide disruptions.
    Data is cached for 2 minutes (or TTL specified by TfL API).

    Args:
        current_user: Authenticated user
        db: Database session

    Returns:
        List of current station disruptions with details

    Raises:
        HTTPException: 503 if TfL API is unavailable
    """
    tfl_service = TfLService(db)
    return await tfl_service.fetch_station_disruptions()


@router.get("/metadata/severity-codes", response_model=list[SeverityCodeResponse])
async def get_severity_codes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SeverityCodeResponse]:
    """
    Get TfL severity code reference data.

    Returns the list of severity codes and their descriptions from TfL API.
    Data is cached for 7 days (or TTL specified by TfL API).

    Args:
        current_user: Authenticated user
        db: Database session

    Returns:
        List of severity codes with levels and descriptions:
        ```json
        [
            {
                "severity_level": 10,
                "description": "Good Service",
                "last_updated": "2025-01-01T00:00:00"
            },
            ...
        ]
        ```

    Raises:
        HTTPException: 503 if TfL API is unavailable
    """
    tfl_service = TfLService(db)
    severity_codes = await tfl_service.fetch_severity_codes()
    return [SeverityCodeResponse.model_validate(code) for code in severity_codes]


@router.get("/metadata/disruption-categories", response_model=list[DisruptionCategoryResponse])
async def get_disruption_categories(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DisruptionCategoryResponse]:
    """
    Get TfL disruption category reference data.

    Returns the list of disruption categories from TfL API.
    Data is cached for 7 days (or TTL specified by TfL API).

    Args:
        current_user: Authenticated user
        db: Database session

    Returns:
        List of disruption categories with names and descriptions:
        ```json
        [
            {
                "category_name": "PlannedWork",
                "description": "Planned engineering work",
                "last_updated": "2025-01-01T00:00:00"
            },
            ...
        ]
        ```

    Raises:
        HTTPException: 503 if TfL API is unavailable
    """
    tfl_service = TfLService(db)
    categories = await tfl_service.fetch_disruption_categories()
    return [DisruptionCategoryResponse.model_validate(cat) for cat in categories]


@router.get("/metadata/stop-types", response_model=list[StopTypeResponse])
async def get_stop_types(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[StopTypeResponse]:
    """
    Get TfL stop point type reference data.

    Returns the list of relevant stop point types (filtered to
    NaptanMetroStation, NaptanRailStation, NaptanBusCoachStation).
    Data is cached for 7 days (or TTL specified by TfL API).

    Args:
        current_user: Authenticated user
        db: Database session

    Returns:
        List of stop types with names and descriptions:
        ```json
        [
            {
                "type_name": "NaptanMetroStation",
                "description": "London Underground station",
                "last_updated": "2025-01-01T00:00:00"
            },
            ...
        ]
        ```

    Raises:
        HTTPException: 503 if TfL API is unavailable
    """
    tfl_service = TfLService(db)
    stop_types = await tfl_service.fetch_stop_types()
    return [StopTypeResponse.model_validate(st) for st in stop_types]


@router.get("/lines/{line_id}/routes", response_model=LineRoutesResponse)
async def get_line_routes(
    line_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LineRoutesResponse:
    """
    Get route variants for a specific line.

    Returns ordered station sequences for each route variant on the line.
    This enables the frontend to show users only reachable stations on specific routes.

    **Example**: For the Northern line, this returns separate routes for:
    - Edgware → Morden via Bank
    - High Barnet → Morden via Bank
    - Edgware → Morden via Charing Cross
    - etc.

    **Note**: Route data must be built first using POST /admin/tfl/build-graph.
    Only "Regular" service routes are returned (Night services excluded for MVP).

    Args:
        line_id: TfL line ID (e.g., "victoria", "northern", "elizabeth-line")
        current_user: Authenticated user
        db: Database session

    Returns:
        Line route variants with ordered station lists

    Raises:
        HTTPException: 404 if line not found, 503 if routes not built yet
    """
    tfl_service = TfLService(db)
    return await tfl_service.get_line_routes(line_id)


@router.get("/stations/{station_tfl_id}/routes", response_model=StationRoutesResponse)
async def get_station_routes(
    station_tfl_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StationRoutesResponse:
    """
    Get all routes passing through a specific station.

    Returns information about which line route variants serve this station.

    **Example**: For Camden Town station, this returns routes from both:
    - Northern line (Edgware branch and High Barnet branch)
    - Including which direction each route travels

    **Note**: Route data must be built first using POST /admin/tfl/build-graph.
    Only "Regular" service routes are returned (Night services excluded for MVP).

    Args:
        station_tfl_id: TfL station ID (e.g., "940GZZLUCTN" for Camden Town)
        current_user: Authenticated user
        db: Database session

    Returns:
        Station route information showing all routes passing through this station

    Raises:
        HTTPException: 404 if station not found, 503 if routes not built yet
    """
    tfl_service = TfLService(db)
    return await tfl_service.get_station_routes(station_tfl_id)


@router.get("/line-states", response_model=list[LineStateResponse])
async def get_line_states(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[LineStateResponse]:
    """
    Get current status of all lines.

    Returns the current disruption/status information for all TfL lines.
    Useful for debugging and understanding which lines have alerts.

    Args:
        current_user: Authenticated user
        db: Database session

    Returns:
        List of line states with current severity information
    """
    tfl_service = TfLService(db)
    disruptions = await tfl_service.fetch_line_disruptions(use_cache=True)

    # Convert disruptions to line states (mode is now included in DisruptionResponse)
    return [
        LineStateResponse(
            line_id=d.line_id,
            line_name=d.line_name,
            mode=d.mode,
            status_severity=d.status_severity,
            status_severity_description=d.status_severity_description,
            reason=d.reason,
        )
        for d in disruptions
    ]


@router.get("/alert-config", response_model=list[AlertConfigResponse])
async def get_alert_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AlertConfigResponse]:
    """
    Get alert configuration showing which severities trigger alerts.

    Returns a list of all severity codes with their alert enabled/disabled status.
    Severity codes are populated by syncing with the TfL API via POST /admin/tfl/sync-metadata.

    Args:
        current_user: Authenticated user
        db: Database session

    Returns:
        List of severity codes with their alert configuration
    """
    tfl_service = TfLService(db)
    config = await tfl_service.get_alert_config()

    return [AlertConfigResponse(**item) for item in config]
