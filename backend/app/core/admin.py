"""Admin authorization utilities."""

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.admin import AdminUser
from app.models.user import User


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
    # Query admin_users table to check if this user is an admin
    result = await db.execute(select(AdminUser).where(AdminUser.user_id == current_user.id))
    admin_user = result.scalar_one_or_none()

    if admin_user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )

    return admin_user
