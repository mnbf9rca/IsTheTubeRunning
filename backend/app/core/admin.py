"""Admin authorization utilities."""

from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.admin import AdminUser
from app.models.user import User


async def get_admin_user(user_id: UUID, db: AsyncSession) -> AdminUser | None:
    """
    Get admin user record if exists, None otherwise.

    This is the core database query used by all admin checks.
    Returns the AdminUser record (with role info) or None.

    Args:
        user_id: UUID of the user to check
        db: Database session

    Returns:
        AdminUser model instance if user is admin, None otherwise
    """
    result = await db.execute(select(AdminUser).where(AdminUser.user_id == user_id))
    return result.scalar_one_or_none()


async def check_is_admin(user_id: UUID, db: AsyncSession) -> bool:
    """
    Check if user has admin privileges without raising exception.

    Use this when you need a boolean admin check (e.g., for /auth/me).
    Returns True if user is admin, False otherwise.

    Args:
        user_id: UUID of the user to check
        db: Database session

    Returns:
        True if user has admin privileges, False otherwise
    """
    admin_user = await get_admin_user(user_id, db)
    return admin_user is not None


async def require_admin(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AdminUser:
    """
    Require that the current user has admin privileges.

    This dependency should be used on admin endpoints to restrict access
    to users in the admin_users table.

    Args:
        current_user: Current authenticated user from get_current_user
        db: Database session

    Returns:
        AdminUser model instance with role information

    Raises:
        HTTPException: 403 Forbidden if user is not an admin
    """
    admin_user = await get_admin_user(current_user.id, db)

    if admin_user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )

    return admin_user
