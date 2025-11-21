"""TfL (Transport for London) data models."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
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
    mode: Mapped[str] = mapped_column(
        String(50),  # Transport mode: "tube", "overground", "dlr", "elizabeth-line", etc.
        nullable=False,
        default="tube",
    )
    route_variants: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,  # Stores ordered route sequences (station lists for each route variant)
        nullable=True,
        default=None,
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
    # Hub information for cross-mode interchanges
    hub_naptan_code: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,  # For fast hub lookups during validation
        comment="TfL hub NaPTAN code for interchange stations",
    )
    hub_common_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Common name for the hub (e.g., 'Seven Sisters')",
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
    disruptions: Mapped[list["StationDisruption"]] = relationship(
        back_populates="station",
        cascade="all, delete-orphan",
        lazy="select",
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

    # Ensure unique connections per line (active records only)
    # Partial unique index allows soft-deleted records to accumulate
    # while maintaining uniqueness for active connections (Issue #230)
    __table_args__ = (
        Index(
            "uq_station_connection_active",
            "from_station_id",
            "to_station_id",
            "line_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_station_connections_from_station", "from_station_id"),
        Index("ix_station_connections_to_station", "to_station_id"),
        Index("ix_station_connections_line", "line_id"),
    )

    def __repr__(self) -> str:
        """String representation of the station connection."""
        return f"<StationConnection(id={self.id}, from={self.from_station_id}, to={self.to_station_id})>"


class SeverityCode(BaseModel):
    """TfL severity code reference data, per transport mode.

    The TfL API returns severity codes that vary by mode (tube, dlr, overground, etc.).
    Each mode has its own set of severity levels with potentially different descriptions.
    """

    __tablename__ = "severity_codes"

    mode_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Transport mode (e.g., 'tube', 'dlr', 'overground')",
    )
    severity_level: Mapped[int] = mapped_column(
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "mode_id",
            "severity_level",
            name="uq_severity_code_mode_level",
        ),
    )

    def __repr__(self) -> str:
        """String representation of the severity code."""
        return (
            f"<SeverityCode(id={self.id}, mode={self.mode_id}, "
            f"level={self.severity_level}, description={self.description})>"
        )


class AlertDisabledSeverity(BaseModel):
    """Severity levels that should NOT trigger alerts.

    This table stores (mode_id, severity_level) combinations that should be
    excluded from alert processing. The default behavior is to alert for all
    severities unless they appear in this table.

    Example: Good Service (severity_level=10) should not trigger alerts.
    """

    __tablename__ = "alert_disabled_severities"

    mode_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Transport mode (e.g., 'tube', 'dlr', 'overground')",
    )
    severity_level: Mapped[int] = mapped_column(
        nullable=False,
        index=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "mode_id",
            "severity_level",
            name="uq_alert_disabled_severity_mode_level",
        ),
    )

    def __repr__(self) -> str:
        """String representation of the alert disabled severity."""
        return f"<AlertDisabledSeverity(id={self.id}, mode={self.mode_id}, level={self.severity_level})>"


class DisruptionCategory(BaseModel):
    """TfL disruption category reference data."""

    __tablename__ = "disruption_categories"

    category_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    def __repr__(self) -> str:
        """String representation of the disruption category."""
        return f"<DisruptionCategory(id={self.id}, name={self.category_name})>"


class LineDisruptionStateLog(BaseModel):
    """Log of TfL line disruption state changes over time.

    This table tracks when line disruption states change (not every check).
    Enables troubleshooting and analytics by providing historical disruption data.

    State changes are detected via content hash (SHA256 of line_id + status + reason).
    Only logged when hash differs from previous state for that line.

    Example use cases:
    - "When did the Bakerloo line disruption start?"
    - "How long was the Central line disrupted?"
    - "Why didn't I get alerted for yesterday's disruption?"
    """

    __tablename__ = "line_disruption_state_logs"

    line_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="TfL line ID (e.g., 'bakerloo', 'victoria')",
    )
    status_severity_description: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Disruption status (e.g., 'Good Service', 'Minor Delays', 'Severe Delays')",
    )
    reason: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="Full disruption reason text (nullable for good service)",
    )
    state_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="SHA256 hash of {line_id, status, reason} for deduplication",
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When this state was detected by the alert service",
    )

    __table_args__ = (
        # Composite index for querying recent states for a line
        Index("ix_line_disruption_logs_line_detected", "line_id", "detected_at"),
    )

    def __repr__(self) -> str:
        """String representation of the line disruption state log."""
        return (
            f"<LineDisruptionStateLog(id={self.id}, line_id={self.line_id}, "
            f"status={self.status_severity_description}, detected_at={self.detected_at})>"
        )


class StopType(BaseModel):
    """TfL stop point type reference data."""

    __tablename__ = "stop_types"

    type_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    def __repr__(self) -> str:
        """String representation of the stop type."""
        return f"<StopType(id={self.id}, name={self.type_name})>"


class StationDisruption(BaseModel):
    """Station-level disruption information.

    Maps to TfL API DisruptedPoint structure.
    Field names match TfL API for clarity (type, appearance).
    """

    __tablename__ = "station_disruptions"

    station_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Disruption type from TfL API (e.g., 'Information', 'Interchange Message')",
    )
    description: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )
    appearance: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Disruption appearance/status from TfL API (e.g., 'PlannedWork', 'RealTime')",
    )
    tfl_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Hash-based identifier: atcoCode + fromDate + toDate + description",
    )
    created_at_source: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Start date from TfL API 'fromDate' field",
    )
    end_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="End date from TfL API 'toDate' field",
    )

    # Relationship
    station: Mapped[Station] = relationship(
        back_populates="disruptions",
        lazy="select",
    )

    __table_args__ = (
        # Note: station_id index already defined via index=True in mapped_column
        Index("ix_station_disruptions_tfl_id", "tfl_id"),
    )

    def __repr__(self) -> str:
        """String representation of the station disruption."""
        return (
            f"<StationDisruption(id={self.id}, station_id={self.station_id}, "
            f"type={self.type}, appearance={self.appearance})>"
        )
