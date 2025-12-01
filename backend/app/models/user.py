"""User-related models."""

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.utils.pii import hash_pii


class User(BaseModel):
    """User model for authenticated users."""

    __tablename__ = "users"

    external_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    auth_provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="auth0",
        server_default="auth0",
    )

    # Relationships
    email_addresses: Mapped[list["EmailAddress"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    phone_numbers: Mapped[list["PhoneNumber"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    verification_codes: Mapped[list["VerificationCode"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # Composite unique constraint on external_id + auth_provider
    __table_args__ = (Index("ix_users_external_id_auth_provider", "external_id", "auth_provider", unique=True),)

    def __repr__(self) -> str:
        """String representation of the user."""
        return f"<User(id={self.id}, external_id={self.external_id}, auth_provider={self.auth_provider})>"


class EmailAddress(BaseModel):
    """Email address associated with a user."""

    __tablename__ = "email_addresses"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )
    contact_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="HMAC-SHA256 hash of email for PII-safe logging",
    )
    verified: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )
    is_primary: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )

    # Relationships
    user: Mapped[User] = relationship(back_populates="email_addresses")

    # Ensure only one primary email per user
    __table_args__ = (Index("ix_email_addresses_user_id_primary", "user_id", "is_primary"),)

    def __init__(self, **kwargs: object) -> None:
        """Initialize email address with auto-computed hash."""
        if "email" in kwargs and "contact_hash" not in kwargs:
            kwargs["contact_hash"] = hash_pii(str(kwargs["email"]))
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        """String representation of the email address."""
        return f"<EmailAddress(id={self.id}, email={self.email}, verified={self.verified})>"


class PhoneNumber(BaseModel):
    """Phone number associated with a user."""

    __tablename__ = "phone_numbers"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    phone: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )
    contact_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="HMAC-SHA256 hash of phone for PII-safe logging",
    )
    verified: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )
    is_primary: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )

    # Relationships
    user: Mapped[User] = relationship(back_populates="phone_numbers")

    # Ensure only one primary phone per user
    __table_args__ = (Index("ix_phone_numbers_user_id_primary", "user_id", "is_primary"),)

    def __init__(self, **kwargs: object) -> None:
        """Initialize phone number with auto-computed hash."""
        if "phone" in kwargs and "contact_hash" not in kwargs:
            kwargs["contact_hash"] = hash_pii(str(kwargs["phone"]))
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        """String representation of the phone number."""
        return f"<PhoneNumber(id={self.id}, phone={self.phone}, verified={self.verified})>"


class VerificationType(str, enum.Enum):
    """Type of verification code."""

    EMAIL = "email"
    SMS = "sms"


class VerificationCode(BaseModel):
    """Verification code for email or phone verification."""

    __tablename__ = "verification_codes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="UUID of the EmailAddress or PhoneNumber being verified",
    )
    code: Mapped[str] = mapped_column(
        String(6),
        nullable=False,
    )
    type: Mapped[VerificationType] = mapped_column(
        Enum(
            VerificationType,
            name="verification_type",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    used: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )

    # Relationships
    user: Mapped[User] = relationship(back_populates="verification_codes")

    # Composite index for faster lookups
    __table_args__ = (Index("ix_verification_codes_user_code_type", "user_id", "code", "type"),)

    @property
    def is_expired(self) -> bool:
        """Check if the verification code has expired."""
        return datetime.now(UTC) > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if the verification code is valid (not used and not expired)."""
        return not self.used and not self.is_expired

    def __repr__(self) -> str:
        """String representation of the verification code."""
        return f"<VerificationCode(id={self.id}, type={self.type}, used={self.used})>"
