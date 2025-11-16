"""Utility functions for admin user management.

This module provides reusable functions for creating and managing admin users,
primarily for local development and testing purposes. These functions are used by
both the CLI tool and test fixtures to maintain DRY principles.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import AdminRole, AdminUser
from app.models.user import User


async def create_user(
    db: AsyncSession,
    external_id: str | None = None,
    auth_provider: str = "cli",
) -> User:
    """
    Create a new user record.

    Args:
        db: Database session
        external_id: Optional external ID (e.g., "auth0|123"). If not provided,
                     generates "cli|<uuid>"
        auth_provider: Auth provider name (default: "cli" for CLI-created users)

    Returns:
        Created User object

    Raises:
        ValueError: If a user with the same external_id and auth_provider already exists
    """
    # Generate external_id if not provided
    if external_id is None:
        external_id = f"cli|{uuid.uuid4().hex[:12]}"

    # Check if user already exists
    result = await db.execute(select(User).where(User.external_id == external_id, User.auth_provider == auth_provider))
    if existing_user := result.scalar_one_or_none():
        msg = (
            f"User with external_id '{external_id}' and auth_provider "
            f"'{auth_provider}' already exists (id: {existing_user.id})"
        )
        raise ValueError(msg)

    # Create user
    user = User(external_id=external_id, auth_provider=auth_provider)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def grant_admin(
    db: AsyncSession,
    user_id: uuid.UUID,
    role: AdminRole = AdminRole.ADMIN,
    granted_by: uuid.UUID | None = None,
) -> AdminUser:
    """
    Grant admin privileges to a user.

    Args:
        db: Database session
        user_id: UUID of user to make admin
        role: Admin role to grant (default: ADMIN)
        granted_by: User ID who granted admin (optional)

    Returns:
        Created AdminUser record

    Raises:
        ValueError: If user doesn't exist or is already an admin
    """
    # Check user exists
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        msg = f"User with id {user_id} not found"
        raise ValueError(msg)

    # Check not already admin
    admin_result = await db.execute(select(AdminUser).where(AdminUser.user_id == user_id))
    if existing_admin := admin_result.scalar_one_or_none():
        msg = f"User {user_id} is already an admin with role {existing_admin.role.value}"
        raise ValueError(msg)

    # Create admin record
    admin = AdminUser(
        user_id=user_id,
        role=role,
        granted_at=datetime.now(UTC),
        granted_by=granted_by,
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    return admin


async def create_admin_user(
    db: AsyncSession,
    external_id: str | None = None,
    auth_provider: str = "cli",
    role: AdminRole = AdminRole.ADMIN,
) -> tuple[User, AdminUser]:
    """
    Create a new user and immediately grant admin privileges.

    This is the primary function for creating admin users in local development.
    It combines user creation and admin grant in a single transaction.

    Args:
        db: Database session
        external_id: Optional external ID (e.g., "auth0|123"). If not provided,
                     generates "cli|<uuid>"
        auth_provider: Auth provider name (default: "cli" for CLI-created users)
        role: Admin role to grant (default: ADMIN)

    Returns:
        Tuple of (User, AdminUser)

    Raises:
        ValueError: If a user with the same external_id and auth_provider already exists
    """
    # Create user
    user = await create_user(db, external_id=external_id, auth_provider=auth_provider)

    # Grant admin privileges
    admin = await grant_admin(db, user_id=user.id, role=role, granted_by=None)

    return user, admin


async def revoke_admin(db: AsyncSession, user_id: uuid.UUID) -> bool:
    """
    Revoke admin privileges from a user.

    Args:
        db: Database session
        user_id: UUID of user to remove admin privileges from

    Returns:
        True if admin was revoked, False if user was not an admin

    Raises:
        ValueError: If user doesn't exist
    """
    # Check user exists
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        msg = f"User with id {user_id} not found"
        raise ValueError(msg)

    # Find admin record
    result = await db.execute(select(AdminUser).where(AdminUser.user_id == user_id))
    admin = result.scalar_one_or_none()
    if not admin:
        return False

    # Delete admin record
    await db.delete(admin)
    await db.commit()
    return True


async def list_admin_users(db: AsyncSession) -> list[tuple[User, AdminUser]]:
    """
    List all admin users.

    Args:
        db: Database session

    Returns:
        List of (User, AdminUser) tuples for all admins
    """
    result = await db.execute(
        select(User, AdminUser).join(AdminUser, User.id == AdminUser.user_id).order_by(AdminUser.granted_at.desc())
    )
    return [(row[0], row[1]) for row in result.all()]


async def list_users(db: AsyncSession, limit: int = 50, offset: int = 0) -> list[User]:
    """
    List all users with pagination.

    Args:
        db: Database session
        limit: Maximum number of users to return (default: 50)
        offset: Number of users to skip (default: 0)

    Returns:
        List of User objects
    """
    result = await db.execute(select(User).order_by(User.created_at.desc()).limit(limit).offset(offset))
    return list(result.scalars().all())


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    """
    Find user by UUID.

    Args:
        db: Database session
        user_id: UUID of user to find

    Returns:
        User object or None if not found
    """
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def find_user_by_external_id(
    db: AsyncSession,
    external_id: str,
    auth_provider: str = "auth0",
) -> User | None:
    """
    Find user by external_id (e.g., Auth0 ID).

    Args:
        db: Database session
        external_id: External ID to search for (e.g., "auth0|123456")
        auth_provider: Auth provider name (default: "auth0")

    Returns:
        User object or None if not found
    """
    result = await db.execute(select(User).where(User.external_id == external_id, User.auth_provider == auth_provider))
    return result.scalar_one_or_none()
