"""Admin API endpoints for system management."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.tfl import BuildGraphResponse
from app.services.tfl_service import TfLService

router = APIRouter(prefix="/admin", tags=["admin"])


# ==================== API Endpoints ====================


@router.post("/tfl/build-graph", response_model=BuildGraphResponse)
async def build_tfl_graph(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BuildGraphResponse:
    """
    Build the station connection graph from TfL API data.

    This endpoint fetches station sequences for all tube lines and populates
    the StationConnection table with bidirectional connections. This is required
    for route validation.

    **Note**: Proper admin authentication will be added in Phase 9. Currently
    requires any authenticated user.

    Args:
        current_user: Authenticated user
        db: Database session

    Returns:
        Build statistics (lines, stations, connections count)

    Raises:
        HTTPException: 503 if TfL API is unavailable, 500 if build fails
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
