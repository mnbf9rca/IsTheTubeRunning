"""Tests for CLI tool.

This module tests the CLI command handlers with real database operations
using the db_session fixture from pytest-postgresql.
"""

import argparse
from datetime import UTC, datetime

import pytest
from app.cli import (
    cmd_create_admin,
    cmd_create_user,
    cmd_grant_admin,
    cmd_list_admins,
    cmd_list_users,
    cmd_revoke_admin,
)
from app.models.admin import AdminRole, AdminUser
from app.models.user import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_cmd_create_admin_success(db_session: AsyncSession, capsys: pytest.CaptureFixture[str]):
    """Test create-admin command creates user and admin in database."""
    args = argparse.Namespace(external_id=None, superadmin=False)

    exit_code = await cmd_create_admin(args, db_session)

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Created admin user successfully" in captured.out

    # Verify user was created in database
    result = await db_session.execute(select(User))
    users = list(result.scalars().all())
    assert len(users) == 1
    assert users[0].auth_provider == "cli"

    # Verify admin was created in database
    result = await db_session.execute(select(AdminUser))
    admins = list(result.scalars().all())
    assert len(admins) == 1
    assert admins[0].role == AdminRole.ADMIN
    assert admins[0].user_id == users[0].id


@pytest.mark.asyncio
async def test_cmd_create_admin_with_custom_external_id(db_session: AsyncSession, capsys: pytest.CaptureFixture[str]):
    """Test create-admin command with custom external_id."""
    args = argparse.Namespace(external_id="auth0|custom123", superadmin=False)

    exit_code = await cmd_create_admin(args, db_session)

    assert exit_code == 0

    # Verify user has custom external_id
    result = await db_session.execute(select(User))
    users = list(result.scalars().all())
    assert len(users) == 1
    assert users[0].external_id == "auth0|custom123"


@pytest.mark.asyncio
async def test_cmd_create_admin_with_superadmin_role(db_session: AsyncSession, capsys: pytest.CaptureFixture[str]):
    """Test create-admin command with superadmin flag."""
    args = argparse.Namespace(external_id=None, superadmin=True)

    exit_code = await cmd_create_admin(args, db_session)

    assert exit_code == 0

    # Verify admin has SUPERADMIN role
    result = await db_session.execute(select(AdminUser))
    admins = list(result.scalars().all())
    assert len(admins) == 1
    assert admins[0].role == AdminRole.SUPERADMIN


@pytest.mark.asyncio
async def test_cmd_create_admin_duplicate_error(db_session: AsyncSession, capsys: pytest.CaptureFixture[str]):
    """Test create-admin command with duplicate external_id."""
    # Create first user
    args1 = argparse.Namespace(external_id="auth0|duplicate", superadmin=False)
    await cmd_create_admin(args1, db_session)

    # Try to create duplicate
    args2 = argparse.Namespace(external_id="auth0|duplicate", superadmin=False)
    exit_code = await cmd_create_admin(args2, db_session)

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Error" in captured.err
    assert "already exists" in captured.err


@pytest.mark.asyncio
async def test_cmd_create_user_success(db_session: AsyncSession, capsys: pytest.CaptureFixture[str]):
    """Test create-user command creates user without admin privileges."""
    args = argparse.Namespace(external_id=None)

    exit_code = await cmd_create_user(args, db_session)

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Created user successfully" in captured.out

    # Verify user was created
    result = await db_session.execute(select(User))
    users = list(result.scalars().all())
    assert len(users) == 1
    assert users[0].auth_provider == "cli"

    # Verify NO admin was created
    result = await db_session.execute(select(AdminUser))
    admins = list(result.scalars().all())
    assert len(admins) == 0


@pytest.mark.asyncio
async def test_cmd_grant_admin_by_uuid_success(db_session: AsyncSession, capsys: pytest.CaptureFixture[str]):
    """Test grant-admin command using UUID."""
    # Create a regular user first
    user = User(external_id="auth0|testuser", auth_provider="auth0")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    args = argparse.Namespace(
        identifier=str(user.id),
        external_id=False,
        provider="auth0",
        superadmin=False,
    )

    exit_code = await cmd_grant_admin(args, db_session)

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Granted admin privileges successfully" in captured.out

    # Verify admin was created
    result = await db_session.execute(select(AdminUser).where(AdminUser.user_id == user.id))
    admin = result.scalar_one_or_none()
    assert admin is not None
    assert admin.role == AdminRole.ADMIN


@pytest.mark.asyncio
async def test_cmd_grant_admin_by_external_id_success(db_session: AsyncSession, capsys: pytest.CaptureFixture[str]):
    """Test grant-admin command using external_id."""
    # Create a regular user first
    user = User(external_id="auth0|test123", auth_provider="auth0")
    db_session.add(user)
    await db_session.commit()

    args = argparse.Namespace(
        identifier="auth0|test123",
        external_id=True,
        provider="auth0",
        superadmin=False,
    )

    exit_code = await cmd_grant_admin(args, db_session)

    assert exit_code == 0

    # Verify admin was created
    result = await db_session.execute(select(AdminUser))
    admins = list(result.scalars().all())
    assert len(admins) == 1


@pytest.mark.asyncio
async def test_cmd_grant_admin_invalid_uuid(db_session: AsyncSession, capsys: pytest.CaptureFixture[str]):
    """Test grant-admin command with invalid UUID."""
    args = argparse.Namespace(
        identifier="not-a-uuid",
        external_id=False,
        provider="auth0",
        superadmin=False,
    )

    exit_code = await cmd_grant_admin(args, db_session)

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Invalid UUID" in captured.err


@pytest.mark.asyncio
async def test_cmd_grant_admin_user_not_found_by_external_id(
    db_session: AsyncSession, capsys: pytest.CaptureFixture[str]
):
    """Test grant-admin when user not found by external_id."""
    args = argparse.Namespace(
        identifier="auth0|notfound",
        external_id=True,
        provider="auth0",
        superadmin=False,
    )

    exit_code = await cmd_grant_admin(args, db_session)

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "not found" in captured.err


@pytest.mark.asyncio
async def test_cmd_revoke_admin_success(db_session: AsyncSession, capsys: pytest.CaptureFixture[str]):
    """Test revoke-admin command removes admin privileges."""
    # Create admin user
    user = User(external_id="auth0|admin", auth_provider="auth0")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    admin = AdminUser(user_id=user.id, role=AdminRole.ADMIN, granted_at=datetime.now(UTC))
    db_session.add(admin)
    await db_session.commit()

    args = argparse.Namespace(
        identifier=str(user.id),
        external_id=False,
        provider="auth0",
    )

    exit_code = await cmd_revoke_admin(args, db_session)

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Revoked admin privileges" in captured.out

    # Verify admin was removed from database
    result = await db_session.execute(select(AdminUser).where(AdminUser.user_id == user.id))
    admin = result.scalar_one_or_none()
    assert admin is None


@pytest.mark.asyncio
async def test_cmd_revoke_admin_not_admin(db_session: AsyncSession, capsys: pytest.CaptureFixture[str]):
    """Test revoke-admin when user is not an admin."""
    # Create regular user (no admin privileges)
    user = User(external_id="auth0|regular", auth_provider="auth0")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    args = argparse.Namespace(
        identifier=str(user.id),
        external_id=False,
        provider="auth0",
    )

    exit_code = await cmd_revoke_admin(args, db_session)

    assert exit_code == 0  # Still returns 0, but with different message
    captured = capsys.readouterr()
    assert "was not an admin" in captured.err


@pytest.mark.asyncio
async def test_cmd_list_admins_empty(db_session: AsyncSession, capsys: pytest.CaptureFixture[str]):
    """Test list-admins command with no admins in database."""
    args = argparse.Namespace()

    exit_code = await cmd_list_admins(args, db_session)

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "No admin users found" in captured.out


@pytest.mark.asyncio
async def test_cmd_list_admins_with_admins(db_session: AsyncSession, capsys: pytest.CaptureFixture[str]):
    """Test list-admins command with admins in database."""
    # Create admin user
    user = User(external_id="auth0|admin1", auth_provider="auth0")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    admin = AdminUser(user_id=user.id, role=AdminRole.ADMIN, granted_at=datetime.now(UTC))
    db_session.add(admin)
    await db_session.commit()

    args = argparse.Namespace()

    exit_code = await cmd_list_admins(args, db_session)

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Found 1 admin user" in captured.out
    assert str(user.id) in captured.out


@pytest.mark.asyncio
async def test_cmd_list_users_empty(db_session: AsyncSession, capsys: pytest.CaptureFixture[str]):
    """Test list-users command with no users in database."""
    args = argparse.Namespace(limit=50, offset=0)

    exit_code = await cmd_list_users(args, db_session)

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "No users found" in captured.out


@pytest.mark.asyncio
async def test_cmd_list_users_with_users(db_session: AsyncSession, capsys: pytest.CaptureFixture[str]):
    """Test list-users command with users in database."""
    # Create user
    user = User(external_id="cli|user1", auth_provider="cli")
    db_session.add(user)
    await db_session.commit()

    args = argparse.Namespace(limit=50, offset=0)

    exit_code = await cmd_list_users(args, db_session)

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Showing 1 user(s)" in captured.out
    assert str(user.id) in captured.out


@pytest.mark.asyncio
async def test_cmd_list_users_with_pagination(db_session: AsyncSession, capsys: pytest.CaptureFixture[str]):
    """Test list-users command respects pagination parameters."""
    # Create multiple users
    for i in range(5):
        user = User(external_id=f"cli|user{i}", auth_provider="cli")
        db_session.add(user)
    await db_session.commit()

    # Test with limit
    args = argparse.Namespace(limit=2, offset=0)
    exit_code = await cmd_list_users(args, db_session)

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Showing 2 user(s)" in captured.out

    # Test with offset
    args = argparse.Namespace(limit=10, offset=3)
    exit_code = await cmd_list_users(args, db_session)

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Showing 2 user(s)" in captured.out  # 5 total - 3 offset = 2
