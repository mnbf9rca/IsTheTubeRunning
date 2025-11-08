"""Pydantic schemas for TfL API data."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ==================== Response Schemas ====================


class LineResponse(BaseModel):
    """Response schema for TfL line data."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tfl_id: str
    name: str
    color: str  # Hex color code (e.g., #0019A8)
    mode: str  # Transport mode: "tube", "overground", "dlr", "elizabeth-line", etc.
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


# ==================== Request Schemas ====================


class RouteSegmentRequest(BaseModel):
    """Single segment in a route (station + line)."""

    station_id: UUID = Field(..., description="Station UUID from database")
    line_id: UUID = Field(..., description="Line UUID from database")


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
