"""Type definitions for TfL API responses.

This module contains Pydantic models for API response structures
that are not part of the pydantic-tfl-api library.
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


class RouteVariant(BaseModel):
    """A single route variant with direction and station sequence."""

    direction: str
    name: str
    service_type: str
    stations: list[str]  # List of station TfL IDs


class StationRouteInfo(BaseModel):
    """Information about a route passing through a station."""

    line_tfl_id: str
    line_name: str
    route_name: str
    service_type: str
    direction: str


class LineRoutesResponse(BaseModel):
    """Response structure for line routes endpoint."""

    line_tfl_id: str
    routes: list[RouteVariant]


class StationRoutesResponse(BaseModel):
    """Response structure for station routes endpoint."""

    station_tfl_id: str
    station_name: str
    routes: list[StationRouteInfo]
