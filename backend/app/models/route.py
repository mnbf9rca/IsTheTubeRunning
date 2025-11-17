"""Route-related models for user commute routes."""

import uuid
from datetime import time
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.helpers.station_resolution import get_canonical_station_id
from app.models.base import BaseModel
from app.models.tfl import Line, Station
from app.models.user import User

if TYPE_CHECKING:
    from app.models.notification import NotificationPreference
    from app.models.route_index import RouteStationIndex


class Route(BaseModel):
    """User's commute route."""

    __tablename__ = "user_routes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        server_default=text("'Europe/London'"),
        comment="IANA timezone for schedule interpretation",
    )

    # Relationships
    user: Mapped["User"] = relationship()
    segments: Mapped[list["RouteSegment"]] = relationship(
        back_populates="route",
        cascade="all, delete-orphan",
        order_by="RouteSegment.sequence",
    )
    schedules: Mapped[list["RouteSchedule"]] = relationship(
        back_populates="route",
        cascade="all, delete-orphan",
    )
    notification_preferences: Mapped[list["NotificationPreference"]] = relationship(
        back_populates="route",
        cascade="all, delete-orphan",
    )
    station_indexes: Mapped[list["RouteStationIndex"]] = relationship(
        back_populates="route",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        """String representation of the route."""
        return f"<Route(id={self.id}, name={self.name}, active={self.active})>"


class RouteSegment(BaseModel):
    """A segment of a route (station + line combination in sequence)."""

    __tablename__ = "user_route_segments"

    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_routes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    station_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stations.id", ondelete="CASCADE"),
        nullable=False,
    )
    line_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lines.id", ondelete="CASCADE"),
        nullable=True,
    )

    # Relationships
    route: Mapped[Route] = relationship(back_populates="segments")
    station: Mapped["Station"] = relationship()
    line: Mapped["Line"] = relationship()

    # Ensure unique sequence per route
    __table_args__ = (
        UniqueConstraint("route_id", "sequence", name="uq_route_segment_sequence"),
        Index("ix_user_route_segments_route_sequence", "route_id", "sequence"),
    )

    @property
    def station_tfl_id(self) -> str:
        """
        Get canonical station identifier from related station.

        Returns hub NaPTAN code if station has one (e.g., 'HUBSVS'),
        otherwise returns the station's TfL ID (e.g., '940GZZLUSVS').

        This implements the "normalize on read" pattern for hub codes (Issue #65).
        """
        return get_canonical_station_id(self.station)

    @property
    def line_tfl_id(self) -> str | None:
        """Get TfL ID from related line. Returns None if line_id is NULL (destination segment)."""
        return self.line.tfl_id if self.line else None

    def __repr__(self) -> str:
        """String representation of the route segment."""
        return f"<RouteSegment(id={self.id}, route={self.route_id}, seq={self.sequence})>"


class RouteSchedule(BaseModel):
    """Schedule for when a route should be monitored for disruptions."""

    __tablename__ = "user_route_schedules"

    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_routes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Days of week as JSON array e.g., ["MON", "TUE", "WED", "THU", "FRI"]
    days_of_week: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
    )
    start_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
    )
    end_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
    )

    # Relationships
    route: Mapped[Route] = relationship(back_populates="schedules")

    def __repr__(self) -> str:
        """String representation of the route schedule."""
        return f"<RouteSchedule(id={self.id}, route={self.route_id}, days={self.days_of_week})>"
