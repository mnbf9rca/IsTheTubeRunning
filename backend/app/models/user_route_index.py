"""Route station index model for fast disruption matching."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.models.user_route import UserRoute


class UserRouteStationIndex(BaseModel):
    """
    Inverted index mapping (line_tfl_id, station_naptan) → route_id.

    Enables O(log n) lookup of routes affected by station-level disruptions.
    One row per station in each user's journey (expanded from sparse route_segments).

    Example:
        User creates route: King's Cross → Leicester Square (Piccadilly)
        Index entries created for ALL intermediate stations:
        - route_id=123, line_tfl_id="piccadilly", station_naptan="940GZZLUKSX"  (King's Cross)
        - route_id=123, line_tfl_id="piccadilly", station_naptan="940GZZLURSQ"  (Russell Square)
        - route_id=123, line_tfl_id="piccadilly", station_naptan="940GZZLUHBN"  (Holborn)
        - route_id=123, line_tfl_id="piccadilly", station_naptan="940GZZLUCGN"  (Covent Garden)
        - route_id=123, line_tfl_id="piccadilly", station_naptan="940GZZLULSQ"  (Leicester Square)

    Updated when:
        - User creates/updates route (Phase 2)
        - Line.route_variants data changes (detected via line_data_version staleness check)

    Soft Delete: This model uses soft delete (deleted_at column from BaseModel).
    Soft deleted via user_route_index_service._delete_existing_index() when rebuilding
    index or cascade from parent route. See Issue #233.
    """

    __tablename__ = "user_route_station_index"

    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_routes.id", ondelete="CASCADE"),
        nullable=False,
        comment="User's route ID",
    )
    line_tfl_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="TfL line ID (e.g., 'piccadilly', 'northern')",
    )
    station_naptan: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Station NaPTAN code (e.g., '940GZZLUKSX')",
    )
    line_data_version: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Copy of Line.last_updated for staleness detection",
    )

    # Relationships
    route: Mapped[UserRoute] = relationship(back_populates="station_indexes")

    __table_args__ = (
        # Primary lookup: "Which routes pass through station X on line Y?"
        Index("ix_user_route_station_index_line_station", "line_tfl_id", "station_naptan"),
        # Cleanup lookup: "Delete all index entries for route Z"
        Index("ix_user_route_station_index_route", "route_id"),
        # Staleness lookup: "Find routes with outdated index data"
        Index("ix_user_route_station_index_line_data_version", "line_data_version"),
    )

    def __repr__(self) -> str:
        """String representation of the route station index entry."""
        return (
            f"<UserRouteStationIndex(route_id={self.route_id}, line={self.line_tfl_id}, station={self.station_naptan})>"
        )
