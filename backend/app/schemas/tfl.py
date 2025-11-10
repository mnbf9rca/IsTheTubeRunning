"""Pydantic schemas for TfL API data."""

from datetime import datetime
from typing import TypedDict
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ==================== Response Schemas ====================


class RouteVariantData(TypedDict, total=False):
    """Route variant structure stored in database."""

    name: str
    service_type: str
    direction: str
    stations: list[str]


class RoutesData(TypedDict, total=False):
    """Routes structure stored in Line.routes JSON field."""

    routes: list[RouteVariantData]


class LineResponse(BaseModel):
    """Response schema for TfL line data."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tfl_id: str
    name: str
    mode: str  # Transport mode: "tube", "overground", "dlr", "elizabeth-line", etc.
    routes: RoutesData | None = None  # Route sequences for branch-aware validation
    last_updated: datetime


class StationResponse(BaseModel):
    """Response schema for TfL station data."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tfl_id: str
    name: str
    latitude: float
    longitude: float
    lines: list[str]  # List of line TfL IDs (e.g., ["victoria", "northern"])
    last_updated: datetime
    hub_naptan_code: str | None  # TfL hub NaPTAN code (e.g., 'HUBSVS' for Seven Sisters)
    hub_common_name: str | None  # Hub common name (e.g., 'Seven Sisters')


class DisruptionResponse(BaseModel):
    """Response schema for TfL disruption data."""

    line_id: str  # TfL line ID
    line_name: str
    status_severity: int  # 0-20 (0=special service, 10=good service, 20=closed)
    status_severity_description: str  # e.g., "Good Service", "Severe Delays"
    reason: str | None = None  # Description of disruption
    created_at: datetime | None = None  # When disruption started (if available)


class StationDisruptionResponse(BaseModel):
    """Response schema for station disruption data."""

    station_id: UUID  # Database station UUID
    station_tfl_id: str  # TfL station ID
    station_name: str
    disruption_category: str | None = None
    description: str
    severity: str | None = None
    tfl_id: str  # TfL disruption ID
    created_at_source: datetime  # When disruption was created at source


class RouteVariant(BaseModel):
    """Schema for a single route variant (ordered station sequence)."""

    name: str = Field(..., description="Route name (e.g., 'Edgware → Morden via Bank')")
    service_type: str = Field(..., description="Service type (e.g., 'Regular', 'Night')")
    direction: str = Field(..., description="Direction: 'inbound' or 'outbound'")
    stations: list[str] = Field(
        ...,
        description="Ordered list of TfL station IDs on this route variant",
    )


class LineRouteResponse(BaseModel):
    """Response schema for line route variants."""

    line_tfl_id: str = Field(..., description="TfL line ID (e.g., 'victoria')")
    routes: list[RouteVariant] = Field(
        ...,
        description="List of route variants for this line",
    )


class StationRouteInfo(BaseModel):
    """Schema for route information for a station."""

    line_tfl_id: str = Field(..., description="TfL line ID")
    line_name: str = Field(..., description="Line name")
    route_name: str = Field(..., description="Route variant name")
    service_type: str = Field(..., description="Service type")
    direction: str = Field(..., description="Direction")


class StationRouteResponse(BaseModel):
    """Response schema for routes passing through a station."""

    station_tfl_id: str = Field(..., description="TfL station ID")
    station_name: str = Field(..., description="Station name")
    routes: list[StationRouteInfo] = Field(
        ...,
        description="Routes passing through this station",
    )


# ==================== Request Schemas ====================


class RouteSegmentRequest(BaseModel):
    """Single segment in a route (station + line)."""

    station_tfl_id: str = Field(..., description="TfL station ID (e.g., '940GZZLUOXC')")
    line_tfl_id: str | None = Field(
        None,
        description="TfL line ID (e.g., 'victoria', 'northern'). NULL means destination segment (no onward travel).",
    )


class RouteValidationRequest(BaseModel):
    """Request to validate a multi-segment route."""

    segments: list[RouteSegmentRequest] = Field(
        ...,
        min_length=2,
        description="Ordered list of stations and lines forming the route. "
        "Must have at least 2 segments (start and end stations).",
    )


class RouteValidationResponse(BaseModel):
    """Response from route validation."""

    valid: bool = Field(..., description="Whether the route is valid")
    message: str = Field(..., description="Human-readable validation result")
    invalid_segment_index: int | None = Field(
        None,
        description="Index of the first invalid segment (0-based), if any",
    )


# ==================== Admin Schemas ====================


class BuildGraphResponse(BaseModel):
    """Response from building the station connection graph."""

    success: bool
    message: str
    lines_count: int = Field(..., description="Number of lines processed")
    stations_count: int = Field(..., description="Number of stations processed")
    connections_count: int = Field(..., description="Number of connections created")
    hubs_count: int = Field(..., description="Number of hub interchange stations")
