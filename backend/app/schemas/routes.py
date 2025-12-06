"""Pydantic schemas for route management."""

from datetime import time
from uuid import UUID
from zoneinfo import ZoneInfo, available_timezones

from app.schemas.tfl import DisruptionResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ==================== Helper Functions ====================


def _validate_day_codes(days: list[str]) -> list[str]:
    """
    Validate day codes - reusable helper.

    Args:
        days: List of day codes to validate

    Returns:
        Validated day codes

    Raises:
        ValueError: If any day code is invalid or duplicates exist
    """
    valid_days = {"MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"}
    if invalid_days := set(days) - valid_days:  # Use named expression
        msg = f"Invalid day codes: {invalid_days}. Valid codes: {valid_days}"
        raise ValueError(msg)

    if len(days) != len(set(days)):
        msg = "Duplicate day codes are not allowed"
        raise ValueError(msg)

    return days


def _validate_time_range(start_time: time | None, end_time: time | None) -> None:
    """
    Validate that end_time is after start_time - reusable helper.

    Only validates if both times are provided (not None).
    This allows partial updates where only one time is being changed.

    Args:
        start_time: Start time (optional)
        end_time: End time (optional)

    Raises:
        ValueError: If both times are provided and end_time <= start_time
    """
    if start_time is not None and end_time is not None and end_time <= start_time:
        msg = "end_time must be after start_time"
        raise ValueError(msg)


def _validate_timezone(tz: str | None) -> str | None:
    """
    Validate timezone is a valid IANA timezone name - reusable helper.

    Uses available_timezones() for deterministic cross-platform validation.
    This ensures consistent behavior on macOS (case-insensitive filesystem)
    and Linux (case-sensitive filesystem).

    Args:
        tz: IANA timezone name (e.g., 'Europe/London', 'America/New_York')

    Returns:
        Validated timezone name

    Raises:
        ValueError: If timezone is invalid or not in canonical form
    """
    if tz is None:
        return None

    # Check against canonical IANA timezone list (deterministic across platforms)
    if tz not in available_timezones():
        msg = f"Invalid IANA timezone: {tz}"
        raise ValueError(msg)

    # Double-check with ZoneInfo (belt and suspenders)
    try:
        ZoneInfo(tz)
    except Exception:
        msg = f"Invalid IANA timezone: {tz}"
        raise ValueError(msg) from None

    return tz


def _validate_quarter_hour(t: time) -> time:
    """
    Validate that time is on a quarter-hour boundary - reusable helper.

    Ensures time falls on 00, 15, 30, or 45 minutes with zero seconds/microseconds.

    Args:
        t: Time to validate

    Returns:
        Validated time

    Raises:
        ValueError: If time is not on a quarter-hour boundary
    """
    if t.minute % 15 != 0 or t.second != 0 or t.microsecond != 0:
        msg = f"Time must be on quarter-hour boundary (00, 15, 30, 45 minutes). Got {t.strftime('%H:%M:%S')}"
        raise ValueError(msg)
    return t


# ==================== Request Schemas ====================


class CreateUserRouteRequest(BaseModel):
    """Request to create a new route."""

    name: str = Field(..., min_length=1, max_length=255, description="Route name")
    description: str | None = Field(None, description="Optional route description")
    active: bool = Field(True, description="Whether the route is active")
    timezone: str = Field(
        default="Europe/London",
        description="IANA timezone for schedule times (e.g., 'Europe/London', 'America/New_York')",
    )

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, tz: str) -> str:
        """Validate timezone using shared helper."""
        result = _validate_timezone(tz)
        # This should never be None since tz is str (not str | None),
        # but check explicitly per code review guidance
        if result is None:
            msg = f"Invalid timezone: {tz}"
            raise ValueError(msg)
        return result


class UpdateUserRouteRequest(BaseModel):
    """Request to update a route's metadata."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    active: bool | None = None
    timezone: str | None = None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, tz: str | None) -> str | None:
        """Validate timezone if provided using shared helper."""
        return _validate_timezone(tz)


class UserRouteSegmentRequest(BaseModel):
    """Single segment in a route (station + line + sequence)."""

    sequence: int = Field(..., ge=0, description="Order of this segment in the route (0-based)")
    station_tfl_id: str = Field(
        ...,
        description=(
            "TfL station ID (e.g., '940GZZLUOXC') or hub NaPTAN code (e.g., 'HUBSVS'). "
            "Hub codes are resolved to specific stations using line context (Issue #65)."
        ),
    )
    line_tfl_id: str | None = Field(
        None, description="TfL line ID (e.g., 'victoria', 'northern'). NULL for destination segment (no onward travel)."
    )


class UpsertUserRouteSegmentsRequest(BaseModel):
    """Request to replace all segments in a route."""

    segments: list[UserRouteSegmentRequest] = Field(
        ...,
        min_length=2,
        description="Ordered list of segments. Must have at least 2 (start and end).",
    )

    @field_validator("segments")
    @classmethod
    def validate_sequences(cls, segments: list[UserRouteSegmentRequest]) -> list[UserRouteSegmentRequest]:
        """
        Validate that sequences are consecutive starting from 0.

        Args:
            segments: List of segments to validate

        Returns:
            Validated segments

        Raises:
            ValueError: If sequences are not consecutive or don't start at 0
        """
        sequences = sorted(seg.sequence for seg in segments)
        expected = list(range(len(segments)))

        if sequences != expected:
            msg = f"Sequences must be consecutive starting from 0. Got {sequences}, expected {expected}"
            raise ValueError(msg)

        return segments


class UpdateUserRouteSegmentRequest(BaseModel):
    """Request to update a single segment."""

    station_tfl_id: str | None = None
    line_tfl_id: str | None = None


class UpsertUserRouteSchedulesRequest(BaseModel):
    """Request to replace all schedules for a route."""

    schedules: list["CreateUserRouteScheduleRequest"] = Field(
        default=[],
        description="List of schedules to set. Empty array deletes all schedules.",
    )


class CreateUserRouteScheduleRequest(BaseModel):
    """Request to create a schedule for a route."""

    days_of_week: list[str] = Field(
        ...,
        min_length=1,
        description="Days when route is active (e.g., ['MON', 'TUE', 'WED'])",
    )
    start_time: time = Field(
        ...,
        description="Start time for monitoring in route's local timezone (naive time)",
    )
    end_time: time = Field(
        ...,
        description="End time for monitoring in route's local timezone (naive time)",
    )

    @field_validator("days_of_week")
    @classmethod
    def validate_days(cls, days: list[str]) -> list[str]:
        """Validate day codes using shared helper."""
        return _validate_day_codes(days)

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_quarter_hour(cls, t: time) -> time:
        """Validate that time is on a quarter-hour boundary using shared helper."""
        return _validate_quarter_hour(t)

    @model_validator(mode="after")
    def validate_time_range(self) -> "CreateUserRouteScheduleRequest":
        """
        Validate that end_time is after start_time using shared helper.

        Returns:
            Validated model instance

        Raises:
            ValueError: If end_time is not after start_time
        """
        _validate_time_range(self.start_time, self.end_time)
        return self


class UpdateUserRouteScheduleRequest(BaseModel):
    """Request to update a schedule."""

    days_of_week: list[str] | None = None
    start_time: time | None = None
    end_time: time | None = None

    @field_validator("days_of_week")
    @classmethod
    def validate_days(cls, days: list[str] | None) -> list[str] | None:
        """Validate day codes if provided using shared helper."""
        if days is None:
            return None
        return _validate_day_codes(days)

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_quarter_hour(cls, t: time | None) -> time | None:
        """Validate that time is on a quarter-hour boundary if provided using shared helper."""
        return None if t is None else _validate_quarter_hour(t)

    @model_validator(mode="after")
    def validate_time_range(self) -> "UpdateUserRouteScheduleRequest":
        """
        Validate that end_time is after start_time if both are provided using shared helper.

        This only validates when both times are present in the same request.
        Partial updates (only one time) are validated at the service layer
        against the existing schedule data.

        Returns:
            Validated model instance

        Raises:
            ValueError: If both times are provided and end_time <= start_time
        """
        _validate_time_range(self.start_time, self.end_time)
        return self


# ==================== Response Schemas ====================


class UserRouteSegmentResponse(BaseModel):
    """Response schema for a route segment."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sequence: int
    station_tfl_id: str
    line_tfl_id: str | None


class UserRouteScheduleResponse(BaseModel):
    """Response schema for a route schedule."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    days_of_week: list[str]
    start_time: time
    end_time: time


class UserRouteResponse(BaseModel):
    """Full response schema for a route with segments and schedules."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    active: bool
    timezone: str
    segments: list[UserRouteSegmentResponse]
    schedules: list[UserRouteScheduleResponse]


class UserRouteListItemResponse(BaseModel):
    """Simplified response schema for route listings."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    active: bool
    timezone: str
    segment_count: int = Field(..., description="Number of segments in the route")
    schedule_count: int = Field(..., description="Number of schedules for the route")


class RouteDisruptionResponse(BaseModel):
    """Response schema for route-specific disruptions.

    Represents a disruption affecting a specific user route, with context
    about which segments and stations are affected.
    """

    model_config = ConfigDict(from_attributes=False)

    route_id: UUID = Field(..., description="ID of the affected route")
    route_name: str = Field(..., description="Name of the affected route")
    disruption: DisruptionResponse = Field(..., description="Details of the TfL disruption")
    affected_segments: list[int] = Field(
        ...,
        description="Segment sequence numbers affected by this disruption (e.g., [0, 1, 2])",
    )
    affected_stations: list[str] = Field(
        ...,
        description="Station NaPTAN codes from this route that are affected",
    )
