"""User schemas - Stub for Phase 3 (Auth0 Integration)."""

from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    """Base user schema."""

    email: EmailStr | None = None


class UserCreate(UserBase):
    """User creation schema."""

    auth0_id: str


class UserResponse(UserBase):
    """User response schema."""

    id: int
    auth0_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        """Pydantic config."""

        from_attributes = True
