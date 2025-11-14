"""Type definitions for TfL API responses.

This module contains Pydantic models for API response structures
that are not part of the pydantic-tfl-api library.

Note: RouteVariant, StationRouteInfo, LineRoutesResponse, and StationRoutesResponse
have been moved to app/schemas/tfl.py to consolidate schema definitions and avoid
duplication. Import from app.schemas.tfl instead.
"""

from pydantic import BaseModel


class NetworkConnection(BaseModel):
    """Connection information in the station network graph.

    Represents a connection between two stations on a specific line,
    used for route validation and network visualization.
    """

    station_id: str
    station_tfl_id: str
    station_name: str
    line_id: str
    line_tfl_id: str
    line_name: str
