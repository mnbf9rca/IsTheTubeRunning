"""Authentication API endpoints."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin import check_is_admin
from app.core.auth import get_current_user
from app.core.database import get_db
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
    is_admin: bool


class AuthReadinessResponse(BaseModel):
    """Auth system readiness check response."""

    ready: bool
    message: str | None = None


@router.get("/ready", response_model=AuthReadinessResponse)
async def auth_readiness_check(
    db: AsyncSession = Depends(get_db),
) -> AuthReadinessResponse:
    """
    Check if the authentication system is ready to accept logins.

    This endpoint checks:
    - Database connectivity
    - Basic auth system health

    Returns:
        Readiness status with optional message explaining any issues.

    Note: This endpoint does NOT require authentication, as it's used by
    the frontend before the login flow begins.
    """
    try:
        # Test database connectivity
        await db.execute(text("SELECT 1"))

        return AuthReadinessResponse(ready=True)

    except Exception as e:
        return AuthReadinessResponse(
            ready=False,
            message=f"Database connection failed: {e!s}",
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Get current authenticated user information.

    This endpoint automatically creates a new user record on first
    authenticated request if the user doesn't exist in the database.

    Returns:
        Current user information including internal ID, timestamps,
        and admin status. Does NOT include external_id or auth_provider
        for security.
    """
    # Check if user has admin privileges
    is_admin = await check_is_admin(current_user.id, db)

    return UserResponse(
        id=current_user.id,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        is_admin=is_admin,
    )
