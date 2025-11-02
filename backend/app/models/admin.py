"""Admin-related models."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class AdminRole(str, enum.Enum):
    """Admin role levels."""

    ADMIN = "admin"
    SUPERADMIN = "superadmin"


class AdminUser(BaseModel):
    """Admin user with elevated permissions."""

    __tablename__ = "admin_users"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    role: Mapped[AdminRole] = mapped_column(
        Enum(
            AdminRole,
            name="admin_role",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=AdminRole.ADMIN,
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    granted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    # Note: We don't create back_populates for user to avoid circular references

    def __repr__(self) -> str:
        """String representation of the admin user."""
        return f"<AdminUser(id={self.id}, user_id={self.user_id}, role={self.role})>"
