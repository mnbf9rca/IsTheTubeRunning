"""TfL (Transport for London) data models."""

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Line(BaseModel):
    """TfL Line model (e.g., Victoria Line, Circle Line)."""

    __tablename__ = "lines"

    tfl_id: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    color: Mapped[str] = mapped_column(
        String(7),  # Hex color code e.g., #0019A8
        nullable=False,
    )
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Relationships
    station_connections: Mapped[list["StationConnection"]] = relationship(
        back_populates="line",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        """String representation of the line."""
        return f"<Line(id={self.id}, name={self.name}, tfl_id={self.tfl_id})>"


class Station(BaseModel):
    """TfL Station model."""

    __tablename__ = "stations"

    tfl_id: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,  # For autocomplete searches
    )
    latitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    longitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    # Store line IDs as JSON array e.g., ["victoria", "northern"]
    lines: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: [],
    )
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Relationships
    connections_from: Mapped[list["StationConnection"]] = relationship(
        foreign_keys="StationConnection.from_station_id",
        back_populates="from_station",
        cascade="all, delete-orphan",
    )
    connections_to: Mapped[list["StationConnection"]] = relationship(
        foreign_keys="StationConnection.to_station_id",
        back_populates="to_station",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        """String representation of the station."""
        return f"<Station(id={self.id}, name={self.name}, tfl_id={self.tfl_id})>"


class StationConnection(BaseModel):
    """Connection between two stations on a specific line (for route validation graph)."""

    __tablename__ = "station_connections"

    from_station_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stations.id", ondelete="CASCADE"),
        nullable=False,
    )
    to_station_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stations.id", ondelete="CASCADE"),
        nullable=False,
    )
    line_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lines.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships
    from_station: Mapped[Station] = relationship(
        foreign_keys=[from_station_id],
        back_populates="connections_from",
    )
    to_station: Mapped[Station] = relationship(
        foreign_keys=[to_station_id],
        back_populates="connections_to",
    )
    line: Mapped[Line] = relationship(back_populates="station_connections")

    # Ensure unique connections per line
    __table_args__ = (
        UniqueConstraint(
            "from_station_id",
            "to_station_id",
            "line_id",
            name="uq_station_connection",
        ),
        Index("ix_station_connections_from_station", "from_station_id"),
        Index("ix_station_connections_to_station", "to_station_id"),
        Index("ix_station_connections_line", "line_id"),
    )

    def __repr__(self) -> str:
        """String representation of the station connection."""
        return f"<StationConnection(id={self.id}, from={self.from_station_id}, to={self.to_station_id})>"
