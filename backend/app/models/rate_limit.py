"""Rate limiting models."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class RateLimitAction(str, enum.Enum):
    """Type of action being rate limited."""

    VERIFY_CODE = "verify_code"  # Verification code request
    ADD_CONTACT_FAILURE = "add_contact_failure"  # Failed contact addition (duplicate)


class RateLimitLog(BaseModel):
    """Log of rate-limited actions for abuse prevention."""

    __tablename__ = "rate_limit_logs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_type: Mapped[RateLimitAction] = mapped_column(
        Enum(
            RateLimitAction,
            name="rate_limit_action",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    resource_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Contact ID or email/phone being verified",
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    # Composite index for efficient rate limit queries
    __table_args__ = (
        Index("ix_rate_limit_user_action_timestamp", "user_id", "action_type", "timestamp"),
        Index("ix_rate_limit_resource_timestamp", "resource_id", "timestamp"),
    )

    def __repr__(self) -> str:
        """String representation of the rate limit log."""
        return f"<RateLimitLog(id={self.id}, action={self.action_type}, resource={self.resource_id})>"
