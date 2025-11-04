"""Pydantic schemas for route management."""

from datetime import time
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ==================== Request Schemas ====================


class CreateRouteRequest(BaseModel):
    """Request to create a new route."""

    name: str = Field(..., min_length=1, max_length=255, description="Route name")
    description: str | None = Field(None, description="Optional route description")
    active: bool = Field(True, description="Whether the route is active")


class UpdateRouteRequest(BaseModel):
    """Request to update a route's metadata."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    active: bool | None = None


class SegmentRequest(BaseModel):
    """Single segment in a route (station + line + sequence)."""

    sequence: int = Field(..., ge=0, description="Order of this segment in the route (0-based)")
    station_id: UUID = Field(..., description="Station UUID from database")
    line_id: UUID = Field(..., description="Line UUID from database")


class UpsertSegmentsRequest(BaseModel):
    """Request to replace all segments in a route."""

    segments: list[SegmentRequest] = Field(
        ...,
        min_length=2,
        description="Ordered list of segments. Must have at least 2 (start and end).",
    )

    @field_validator("segments")
    @classmethod
    def validate_sequences(cls, segments: list[SegmentRequest]) -> list[SegmentRequest]:
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


class UpdateSegmentRequest(BaseModel):
    """Request to update a single segment."""

    station_id: UUID | None = None
    line_id: UUID | None = None


class CreateScheduleRequest(BaseModel):
    """Request to create a schedule for a route."""

    days_of_week: list[str] = Field(
        ...,
        min_length=1,
        description="Days when route is active (e.g., ['MON', 'TUE', 'WED'])",
    )
    start_time: time = Field(..., description="Start time for monitoring (local London time)")
    end_time: time = Field(..., description="End time for monitoring (local London time)")

    @field_validator("days_of_week")
    @classmethod
    def validate_days(cls, days: list[str]) -> list[str]:
        """
        Validate day codes.

        Args:
            days: List of day codes

        Returns:
            Validated day codes

        Raises:
            ValueError: If any day code is invalid
        """
        valid_days = {"MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"}
        invalid_days = set(days) - valid_days

        if invalid_days:
            msg = f"Invalid day codes: {invalid_days}. Valid codes: {valid_days}"
            raise ValueError(msg)

        # Check for duplicates
        if len(days) != len(set(days)):
            msg = "Duplicate day codes are not allowed"
            raise ValueError(msg)

        return days

    @field_validator("end_time")
    @classmethod
    def validate_time_range(cls, end_time: time, info: Any) -> time:  # noqa: ANN401
        """
        Validate that end_time is after start_time.

        Args:
            end_time: End time
            info: Validation info containing other fields

        Returns:
            Validated end time

        Raises:
            ValueError: If end_time is not after start_time
        """
        start_time = info.data.get("start_time")
        if start_time and end_time <= start_time:
            msg = "end_time must be after start_time"
            raise ValueError(msg)

        return end_time


class UpdateScheduleRequest(BaseModel):
    """Request to update a schedule."""

    days_of_week: list[str] | None = None
    start_time: time | None = None
    end_time: time | None = None

    @field_validator("days_of_week")
    @classmethod
    def validate_days(cls, days: list[str] | None) -> list[str] | None:
        """Validate day codes if provided."""
        if days is None:
            return None

        valid_days = {"MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"}
        invalid_days = set(days) - valid_days

        if invalid_days:
            msg = f"Invalid day codes: {invalid_days}. Valid codes: {valid_days}"
            raise ValueError(msg)

        if len(days) != len(set(days)):
            msg = "Duplicate day codes are not allowed"
            raise ValueError(msg)

        return days


# ==================== Response Schemas ====================


class SegmentResponse(BaseModel):
    """Response schema for a route segment."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sequence: int
    station_id: UUID
    line_id: UUID


class ScheduleResponse(BaseModel):
    """Response schema for a route schedule."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    days_of_week: list[str]
    start_time: time
    end_time: time


class RouteResponse(BaseModel):
    """Full response schema for a route with segments and schedules."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    active: bool
    segments: list[SegmentResponse]
    schedules: list[ScheduleResponse]


class RouteListItemResponse(BaseModel):
    """Simplified response schema for route listings."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    active: bool
    segment_count: int = Field(..., description="Number of segments in the route")
    schedule_count: int = Field(..., description="Number of schedules for the route")
