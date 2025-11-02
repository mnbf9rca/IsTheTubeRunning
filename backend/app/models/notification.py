"""Notification-related models."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.route import Route
    from app.models.user import User


class NotificationMethod(str, enum.Enum):
    """Notification delivery method."""

    EMAIL = "email"
    SMS = "sms"


class NotificationStatus(str, enum.Enum):
    """Notification delivery status."""

    SENT = "sent"
    FAILED = "failed"
    PENDING = "pending"


class NotificationPreference(BaseModel):
    """User's notification preferences for a route."""

    __tablename__ = "notification_preferences"

    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("routes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    method: Mapped[NotificationMethod] = mapped_column(
        Enum(
            NotificationMethod,
            name="notification_method",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    # One of these must be set based on method
    target_email_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("email_addresses.id", ondelete="CASCADE"),
        nullable=True,
    )
    target_phone_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("phone_numbers.id", ondelete="CASCADE"),
        nullable=True,
    )

    # Relationships
    route: Mapped["Route"] = relationship()

    # Ensure one and only one target is set
    __table_args__ = (
        CheckConstraint(
            "(target_email_id IS NOT NULL AND target_phone_id IS NULL) OR "
            "(target_email_id IS NULL AND target_phone_id IS NOT NULL)",
            name="ck_notification_preference_target",
        ),
        Index("ix_notification_preferences_route", "route_id"),
    )

    def __repr__(self) -> str:
        """String representation of the notification preference."""
        return f"<NotificationPreference(id={self.id}, method={self.method})>"


class NotificationLog(BaseModel):
    """Log of sent notifications."""

    __tablename__ = "notification_logs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("routes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,  # For time-based queries
    )
    method: Mapped[NotificationMethod] = mapped_column(
        Enum(
            NotificationMethod,
            name="notification_method",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(
            NotificationStatus,
            name="notification_status",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship()
    route: Mapped["Route"] = relationship()

    # Composite index for recent notifications by user
    __table_args__ = (
        Index("ix_notification_logs_user_sent", "user_id", "sent_at"),
        Index("ix_notification_logs_route_sent", "route_id", "sent_at"),
    )

    def __repr__(self) -> str:
        """String representation of the notification log."""
        return f"<NotificationLog(id={self.id}, method={self.method}, status={self.status})>"
