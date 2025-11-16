"""Tests for admin helper utility functions.

This module tests all functions in app/utils/admin_helpers.py to ensure 100% coverage
and validate correct behavior for admin user management operations.
"""

import uuid

import pytest
from app.models.admin import AdminRole, AdminUser
from app.models.user import User
from app.utils.admin_helpers import (
    create_admin_user,
    create_user,
    find_user_by_external_id,
    get_user_by_id,
    grant_admin,
    list_admin_users,
    list_users,
    revoke_admin,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Test create_user function


@pytest.mark.asyncio
async def test_create_user_with_default_values(db_session: AsyncSession):
    """Test creating a user with default external_id and auth_provider."""
    user = await create_user(db_session)

    assert user.id is not None
    assert user.external_id.startswith("cli|")
    assert user.auth_provider == "cli"
    assert user.created_at is not None


@pytest.mark.asyncio
async def test_create_user_with_custom_external_id(db_session: AsyncSession):
    """Test creating a user with custom external_id."""
    custom_id = "auth0|custom123"
    user = await create_user(db_session, external_id=custom_id, auth_provider="auth0")

    assert user.external_id == custom_id
    assert user.auth_provider == "auth0"


@pytest.mark.asyncio
async def test_create_user_duplicate_external_id_raises_error(db_session: AsyncSession):
    """Test that creating a user with duplicate external_id raises ValueError."""
    external_id = "auth0|duplicate"

    # Create first user
    await create_user(db_session, external_id=external_id, auth_provider="auth0")

    # Attempt to create duplicate - should raise ValueError
    with pytest.raises(ValueError, match=r".*") as exc_info:
        await create_user(db_session, external_id=external_id, auth_provider="auth0")

    assert "already exists" in str(exc_info.value)
    assert external_id in str(exc_info.value)


@pytest.mark.asyncio
async def test_create_user_same_external_id_different_provider_succeeds(
    db_session: AsyncSession,
):
    """Test that same external_id with different provider creates separate users."""
    external_id = "user123"

    # Create user with auth0 provider
    user1 = await create_user(db_session, external_id=external_id, auth_provider="auth0")

    # Create user with cli provider (same external_id, different provider)
    user2 = await create_user(db_session, external_id=external_id, auth_provider="cli")

    assert user1.id != user2.id
    assert user1.external_id == user2.external_id
    assert user1.auth_provider != user2.auth_provider


# Test grant_admin function


@pytest.mark.asyncio
async def test_grant_admin_to_existing_user(db_session: AsyncSession, test_user: User):
    """Test granting admin privileges to an existing user."""
    admin = await grant_admin(db_session, user_id=test_user.id)

    assert admin.id is not None
    assert admin.user_id == test_user.id
    assert admin.role == AdminRole.ADMIN
    assert admin.granted_at is not None
    assert admin.granted_by is None


@pytest.mark.asyncio
async def test_grant_admin_with_superadmin_role(db_session: AsyncSession, test_user: User):
    """Test granting superadmin role."""
    admin = await grant_admin(db_session, user_id=test_user.id, role=AdminRole.SUPERADMIN)

    assert admin.role == AdminRole.SUPERADMIN


@pytest.mark.asyncio
async def test_grant_admin_with_granted_by(db_session: AsyncSession):
    """Test granting admin with granted_by field set."""
    # Create granter user
    granter = await create_user(db_session, external_id="granter|123")

    # Create grantee user
    grantee = await create_user(db_session, external_id="grantee|123")

    # Grant admin with granted_by
    admin = await grant_admin(db_session, user_id=grantee.id, granted_by=granter.id)

    assert admin.granted_by == granter.id


@pytest.mark.asyncio
async def test_grant_admin_to_nonexistent_user_raises_error(db_session: AsyncSession):
    """Test that granting admin to non-existent user raises ValueError."""
    fake_id = uuid.uuid4()

    with pytest.raises(ValueError, match=r".*") as exc_info:
        await grant_admin(db_session, user_id=fake_id)

    assert "not found" in str(exc_info.value)
    assert str(fake_id) in str(exc_info.value)


@pytest.mark.asyncio
async def test_grant_admin_to_existing_admin_raises_error(db_session: AsyncSession, test_user: User):
    """Test that granting admin to already-admin user raises ValueError."""
    # Grant admin first time
    await grant_admin(db_session, user_id=test_user.id)

    # Attempt to grant again - should raise ValueError
    with pytest.raises(ValueError, match=r".*") as exc_info:
        await grant_admin(db_session, user_id=test_user.id)

    assert "already an admin" in str(exc_info.value)


# Test create_admin_user function


@pytest.mark.asyncio
async def test_create_admin_user_with_defaults(db_session: AsyncSession):
    """Test creating an admin user with default values."""
    user, admin = await create_admin_user(db_session)

    assert user.id is not None
    assert user.external_id.startswith("cli|")
    assert user.auth_provider == "cli"
    assert admin.user_id == user.id
    assert admin.role == AdminRole.ADMIN


@pytest.mark.asyncio
async def test_create_admin_user_with_custom_values(db_session: AsyncSession):
    """Test creating an admin user with custom external_id and role."""
    external_id = "auth0|admin123"
    user, admin = await create_admin_user(
        db_session,
        external_id=external_id,
        auth_provider="auth0",
        role=AdminRole.SUPERADMIN,
    )

    assert user.external_id == external_id
    assert user.auth_provider == "auth0"
    assert admin.role == AdminRole.SUPERADMIN


@pytest.mark.asyncio
async def test_create_admin_user_duplicate_external_id_raises_error(
    db_session: AsyncSession,
):
    """Test that creating admin user with duplicate external_id raises ValueError."""
    external_id = "auth0|duplicate_admin"

    # Create first admin user
    await create_admin_user(db_session, external_id=external_id, auth_provider="auth0")

    # Attempt to create duplicate - should raise ValueError
    with pytest.raises(ValueError, match=r".*") as exc_info:
        await create_admin_user(db_session, external_id=external_id, auth_provider="auth0")

    assert "already exists" in str(exc_info.value)


# Test revoke_admin function


@pytest.mark.asyncio
async def test_revoke_admin_from_admin_user(db_session: AsyncSession, test_user: User):
    """Test revoking admin privileges from an admin user."""
    # Grant admin first
    await grant_admin(db_session, user_id=test_user.id)

    # Revoke admin
    was_revoked = await revoke_admin(db_session, user_id=test_user.id)

    assert was_revoked is True

    # Verify admin record is deleted
    result = await db_session.execute(select(AdminUser).where(AdminUser.user_id == test_user.id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_revoke_admin_from_non_admin_user(db_session: AsyncSession, test_user: User):
    """Test revoking admin from a user who is not an admin."""
    was_revoked = await revoke_admin(db_session, user_id=test_user.id)

    assert was_revoked is False


@pytest.mark.asyncio
async def test_revoke_admin_from_nonexistent_user_raises_error(db_session: AsyncSession):
    """Test that revoking admin from non-existent user raises ValueError."""
    fake_id = uuid.uuid4()

    with pytest.raises(ValueError, match=r".*") as exc_info:
        await revoke_admin(db_session, user_id=fake_id)

    assert "not found" in str(exc_info.value)


# Test list_admin_users function


@pytest.mark.asyncio
async def test_list_admin_users_empty(db_session: AsyncSession):
    """Test listing admin users when there are none."""
    admins = await list_admin_users(db_session)

    assert admins == []


@pytest.mark.asyncio
async def test_list_admin_users_single(db_session: AsyncSession):
    """Test listing admin users with one admin."""
    user, admin = await create_admin_user(db_session)

    admins = await list_admin_users(db_session)

    assert len(admins) == 1
    assert admins[0][0].id == user.id
    assert admins[0][1].id == admin.id


@pytest.mark.asyncio
async def test_list_admin_users_multiple(db_session: AsyncSession):
    """Test listing multiple admin users."""
    # Create 3 admin users
    user1, _admin1 = await create_admin_user(db_session, external_id="admin1")
    user2, _admin2 = await create_admin_user(db_session, external_id="admin2")
    user3, _admin3 = await create_admin_user(db_session, external_id="admin3", role=AdminRole.SUPERADMIN)

    admins = await list_admin_users(db_session)

    assert len(admins) == 3

    # Extract user IDs from results
    admin_user_ids = {admin_tuple[0].id for admin_tuple in admins}
    assert user1.id in admin_user_ids
    assert user2.id in admin_user_ids
    assert user3.id in admin_user_ids


@pytest.mark.asyncio
async def test_list_admin_users_ordered_by_granted_at(db_session: AsyncSession):
    """Test that admin users are ordered by granted_at descending (newest first)."""
    # Create admin users sequentially
    user1, _admin1 = await create_admin_user(db_session, external_id="admin1")
    user2, _admin2 = await create_admin_user(db_session, external_id="admin2")
    user3, _admin3 = await create_admin_user(db_session, external_id="admin3")

    admins = await list_admin_users(db_session)

    # Should be ordered newest first
    assert admins[0][0].id == user3.id
    assert admins[1][0].id == user2.id
    assert admins[2][0].id == user1.id


# Test list_users function


@pytest.mark.asyncio
async def test_list_users_empty(db_session: AsyncSession):
    """Test listing users when there are none."""
    users = await list_users(db_session)

    assert users == []


@pytest.mark.asyncio
async def test_list_users_single(db_session: AsyncSession, test_user: User):
    """Test listing users with one user."""
    users = await list_users(db_session)

    assert len(users) == 1
    assert users[0].id == test_user.id


@pytest.mark.asyncio
async def test_list_users_multiple(db_session: AsyncSession):
    """Test listing multiple users."""
    # Create 5 users
    user1 = await create_user(db_session, external_id="user1")
    user2 = await create_user(db_session, external_id="user2")
    user3 = await create_user(db_session, external_id="user3")
    user4 = await create_user(db_session, external_id="user4")
    user5 = await create_user(db_session, external_id="user5")

    users = await list_users(db_session)

    assert len(users) == 5

    # Extract user IDs
    user_ids = {user.id for user in users}
    assert user1.id in user_ids
    assert user2.id in user_ids
    assert user3.id in user_ids
    assert user4.id in user_ids
    assert user5.id in user_ids


@pytest.mark.asyncio
async def test_list_users_with_limit(db_session: AsyncSession):
    """Test listing users with limit parameter."""
    # Create 10 users
    for i in range(10):
        await create_user(db_session, external_id=f"user{i}")

    users = await list_users(db_session, limit=5)

    assert len(users) == 5


@pytest.mark.asyncio
async def test_list_users_with_offset(db_session: AsyncSession):
    """Test listing users with offset parameter."""
    # Create 10 users
    created_users = []
    for i in range(10):
        user = await create_user(db_session, external_id=f"user{i}")
        created_users.append(user)

    # Get first page
    first_page = await list_users(db_session, limit=5, offset=0)
    # Get second page
    second_page = await list_users(db_session, limit=5, offset=5)

    assert len(first_page) == 5
    assert len(second_page) == 5

    # Ensure no overlap (users are ordered by created_at desc, so newest first)
    first_page_ids = {user.id for user in first_page}
    second_page_ids = {user.id for user in second_page}
    assert len(first_page_ids & second_page_ids) == 0


@pytest.mark.asyncio
async def test_list_users_ordered_by_created_at(db_session: AsyncSession):
    """Test that users are ordered by created_at descending (newest first)."""
    # Create users sequentially
    user1 = await create_user(db_session, external_id="user1")
    user2 = await create_user(db_session, external_id="user2")
    user3 = await create_user(db_session, external_id="user3")

    users = await list_users(db_session)

    # Should be ordered newest first
    assert users[0].id == user3.id
    assert users[1].id == user2.id
    assert users[2].id == user1.id


# Test get_user_by_id function


@pytest.mark.asyncio
async def test_get_user_by_id_existing_user(db_session: AsyncSession, test_user: User):
    """Test getting an existing user by ID."""
    user = await get_user_by_id(db_session, test_user.id)

    assert user is not None
    assert user.id == test_user.id


@pytest.mark.asyncio
async def test_get_user_by_id_nonexistent_user(db_session: AsyncSession):
    """Test getting a non-existent user by ID returns None."""
    fake_id = uuid.uuid4()
    user = await get_user_by_id(db_session, fake_id)

    assert user is None


# Test find_user_by_external_id function


@pytest.mark.asyncio
async def test_find_user_by_external_id_existing_user(db_session: AsyncSession):
    """Test finding an existing user by external_id."""
    external_id = "auth0|findme123"
    created_user = await create_user(db_session, external_id=external_id, auth_provider="auth0")

    user = await find_user_by_external_id(db_session, external_id, auth_provider="auth0")

    assert user is not None
    assert user.id == created_user.id
    assert user.external_id == external_id


@pytest.mark.asyncio
async def test_find_user_by_external_id_nonexistent_user(db_session: AsyncSession):
    """Test finding a non-existent user by external_id returns None."""
    user = await find_user_by_external_id(db_session, "nonexistent|123", auth_provider="auth0")

    assert user is None


@pytest.mark.asyncio
async def test_find_user_by_external_id_wrong_provider(db_session: AsyncSession):
    """Test finding a user with correct external_id but wrong provider returns None."""
    external_id = "user123"
    await create_user(db_session, external_id=external_id, auth_provider="auth0")

    # Search with wrong provider
    user = await find_user_by_external_id(db_session, external_id, auth_provider="cli")

    assert user is None


@pytest.mark.asyncio
async def test_find_user_by_external_id_default_auth0_provider(db_session: AsyncSession):
    """Test that find_user_by_external_id defaults to auth0 provider."""
    external_id = "auth0|default123"
    created_user = await create_user(db_session, external_id=external_id, auth_provider="auth0")

    # Call without auth_provider argument (should default to "auth0")
    user = await find_user_by_external_id(db_session, external_id)

    assert user is not None
    assert user.id == created_user.id
