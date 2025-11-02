"""Authentication API endpoints."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from app.core.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


class UserResponse(BaseModel):
    """
    User information response.

    Note: external_id and auth_provider are intentionally excluded
    for privacy and security reasons.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get current authenticated user information.

    This endpoint automatically creates a new user record on first
    authenticated request if the user doesn't exist in the database.

    Returns:
        Current user information including internal ID and timestamps.
        Does NOT include external_id or auth_provider for security.
    """
    return current_user
