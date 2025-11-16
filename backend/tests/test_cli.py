"""Tests for CLI tool.

This module tests the CLI command handlers to ensure proper integration
with admin_helpers and correct error handling.
"""

import argparse
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.cli import (
    cmd_create_admin,
    cmd_create_user,
    cmd_grant_admin,
    cmd_list_admins,
    cmd_list_users,
    cmd_revoke_admin,
)
from app.models.admin import AdminRole


@pytest.mark.asyncio
async def test_cmd_create_admin_success(capsys: pytest.CaptureFixture[str]):
    """Test create-admin command with default parameters."""
    args = argparse.Namespace(external_id=None, superadmin=False)

    mock_user = MagicMock(
        id=uuid.uuid4(),
        external_id="cli|test123",
        auth_provider="cli",
    )
    mock_admin = MagicMock(
        role=AdminRole.ADMIN,
        granted_at="2025-01-01 12:00:00",
    )

    with patch("app.cli.create_admin_user", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = (mock_user, mock_admin)

        exit_code = await cmd_create_admin(args)

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Created admin user successfully" in captured.out
    assert str(mock_user.id) in captured.out
    assert "cli|test123" in captured.out


@pytest.mark.asyncio
async def test_cmd_create_admin_with_custom_external_id(capsys: pytest.CaptureFixture[str]):
    """Test create-admin command with custom external_id."""
    args = argparse.Namespace(external_id="auth0|custom", superadmin=False)

    mock_user = MagicMock(
        id=uuid.uuid4(),
        external_id="auth0|custom",
        auth_provider="cli",
    )
    mock_admin = MagicMock(
        role=AdminRole.ADMIN,
        granted_at="2025-01-01 12:00:00",
    )

    with patch("app.cli.create_admin_user", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = (mock_user, mock_admin)

        exit_code = await cmd_create_admin(args)

    assert exit_code == 0
    mock_create.assert_called_once()
    call_kwargs = mock_create.call_args[1]
    assert call_kwargs["external_id"] == "auth0|custom"


@pytest.mark.asyncio
async def test_cmd_create_admin_with_superadmin_role(capsys: pytest.CaptureFixture[str]):
    """Test create-admin command with superadmin flag."""
    args = argparse.Namespace(external_id=None, superadmin=True)

    mock_user = MagicMock(id=uuid.uuid4(), external_id="cli|test", auth_provider="cli")
    mock_admin = MagicMock(role=AdminRole.SUPERADMIN, granted_at="2025-01-01 12:00:00")

    with patch("app.cli.create_admin_user", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = (mock_user, mock_admin)

        exit_code = await cmd_create_admin(args)

    assert exit_code == 0
    call_kwargs = mock_create.call_args[1]
    assert call_kwargs["role"] == AdminRole.SUPERADMIN


@pytest.mark.asyncio
async def test_cmd_create_admin_duplicate_error(capsys: pytest.CaptureFixture[str]):
    """Test create-admin command with duplicate external_id."""
    args = argparse.Namespace(external_id="auth0|duplicate", superadmin=False)

    with patch("app.cli.create_admin_user", new_callable=AsyncMock) as mock_create:
        mock_create.side_effect = ValueError("User already exists")

        exit_code = await cmd_create_admin(args)

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Error" in captured.err
    assert "User already exists" in captured.err


@pytest.mark.asyncio
async def test_cmd_create_user_success(capsys: pytest.CaptureFixture[str]):
    """Test create-user command."""
    args = argparse.Namespace(external_id=None)

    mock_user = MagicMock(
        id=uuid.uuid4(),
        external_id="cli|user123",
        auth_provider="cli",
        created_at="2025-01-01 12:00:00",
    )

    with patch("app.cli.create_user", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_user

        exit_code = await cmd_create_user(args)

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Created user successfully" in captured.out
    assert str(mock_user.id) in captured.out


@pytest.mark.asyncio
async def test_cmd_grant_admin_by_uuid_success(capsys: pytest.CaptureFixture[str]):
    """Test grant-admin command using UUID."""
    user_id = uuid.uuid4()
    args = argparse.Namespace(
        identifier=str(user_id),
        external_id=False,
        provider="auth0",
        superadmin=False,
    )

    mock_admin = MagicMock(role=AdminRole.ADMIN, granted_at="2025-01-01 12:00:00")
    mock_user = MagicMock(id=user_id, external_id="auth0|test", auth_provider="auth0")

    with (
        patch("app.cli.grant_admin", new_callable=AsyncMock) as mock_grant,
        patch("app.cli.get_user_by_id", new_callable=AsyncMock) as mock_get,
    ):
        mock_grant.return_value = mock_admin
        mock_get.return_value = mock_user

        exit_code = await cmd_grant_admin(args)

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Granted admin privileges successfully" in captured.out


@pytest.mark.asyncio
async def test_cmd_grant_admin_by_external_id_success(capsys: pytest.CaptureFixture[str]):
    """Test grant-admin command using external_id."""
    user_id = uuid.uuid4()
    args = argparse.Namespace(
        identifier="auth0|test123",
        external_id=True,
        provider="auth0",
        superadmin=False,
    )

    mock_user = MagicMock(id=user_id, external_id="auth0|test123", auth_provider="auth0")
    mock_admin = MagicMock(role=AdminRole.ADMIN, granted_at="2025-01-01 12:00:00")

    with (
        patch("app.cli.find_user_by_external_id", new_callable=AsyncMock) as mock_find,
        patch("app.cli.grant_admin", new_callable=AsyncMock) as mock_grant,
        patch("app.cli.get_user_by_id", new_callable=AsyncMock) as mock_get,
    ):
        mock_find.return_value = mock_user
        mock_grant.return_value = mock_admin
        mock_get.return_value = mock_user

        exit_code = await cmd_grant_admin(args)

    assert exit_code == 0


@pytest.mark.asyncio
async def test_cmd_grant_admin_invalid_uuid(capsys: pytest.CaptureFixture[str]):
    """Test grant-admin command with invalid UUID."""
    args = argparse.Namespace(
        identifier="not-a-uuid",
        external_id=False,
        provider="auth0",
        superadmin=False,
    )

    exit_code = await cmd_grant_admin(args)

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Invalid UUID" in captured.err


@pytest.mark.asyncio
async def test_cmd_grant_admin_user_not_found_by_external_id(capsys: pytest.CaptureFixture[str]):
    """Test grant-admin when user not found by external_id."""
    args = argparse.Namespace(
        identifier="auth0|notfound",
        external_id=True,
        provider="auth0",
        superadmin=False,
    )

    with patch("app.cli.find_user_by_external_id", new_callable=AsyncMock) as mock_find:
        mock_find.return_value = None

        exit_code = await cmd_grant_admin(args)

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "not found" in captured.err


@pytest.mark.asyncio
async def test_cmd_revoke_admin_success(capsys: pytest.CaptureFixture[str]):
    """Test revoke-admin command."""
    user_id = uuid.uuid4()
    args = argparse.Namespace(
        identifier=str(user_id),
        external_id=False,
        provider="auth0",
    )

    with patch("app.cli.revoke_admin", new_callable=AsyncMock) as mock_revoke:
        mock_revoke.return_value = True

        exit_code = await cmd_revoke_admin(args)

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Revoked admin privileges" in captured.out


@pytest.mark.asyncio
async def test_cmd_revoke_admin_not_admin(capsys: pytest.CaptureFixture[str]):
    """Test revoke-admin when user is not an admin."""
    user_id = uuid.uuid4()
    args = argparse.Namespace(
        identifier=str(user_id),
        external_id=False,
        provider="auth0",
    )

    with patch("app.cli.revoke_admin", new_callable=AsyncMock) as mock_revoke:
        mock_revoke.return_value = False

        exit_code = await cmd_revoke_admin(args)

    assert exit_code == 0  # Still returns 0, but with different message
    captured = capsys.readouterr()
    assert "was not an admin" in captured.err


@pytest.mark.asyncio
async def test_cmd_list_admins_empty(capsys: pytest.CaptureFixture[str]):
    """Test list-admins command with no admins."""
    args = argparse.Namespace()

    with patch("app.cli.list_admin_users", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = []

        exit_code = await cmd_list_admins(args)

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "No admin users found" in captured.out


@pytest.mark.asyncio
async def test_cmd_list_admins_with_admins(capsys: pytest.CaptureFixture[str]):
    """Test list-admins command with admins."""
    args = argparse.Namespace()

    mock_user = MagicMock(
        id=uuid.uuid4(),
        external_id="auth0|admin1",
    )
    mock_admin = MagicMock(
        role=AdminRole.ADMIN,
        granted_at=MagicMock(strftime=lambda fmt: "2025-01-01 12:00:00"),
    )

    with patch("app.cli.list_admin_users", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = [(mock_user, mock_admin)]

        exit_code = await cmd_list_admins(args)

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Found 1 admin user" in captured.out


@pytest.mark.asyncio
async def test_cmd_list_users_empty(capsys: pytest.CaptureFixture[str]):
    """Test list-users command with no users."""
    args = argparse.Namespace(limit=50, offset=0)

    with patch("app.cli.list_users", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = []

        exit_code = await cmd_list_users(args)

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "No users found" in captured.out


@pytest.mark.asyncio
async def test_cmd_list_users_with_users(capsys: pytest.CaptureFixture[str]):
    """Test list-users command with users."""
    args = argparse.Namespace(limit=50, offset=0)

    mock_user = MagicMock(
        id=uuid.uuid4(),
        external_id="cli|user1",
        auth_provider="cli",
        created_at=MagicMock(strftime=lambda fmt: "2025-01-01 12:00:00"),
    )

    with patch("app.cli.list_users", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = [mock_user]

        exit_code = await cmd_list_users(args)

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Showing 1 user(s)" in captured.out
    assert str(mock_user.id) in captured.out


@pytest.mark.asyncio
async def test_cmd_list_users_with_pagination(capsys: pytest.CaptureFixture[str]):
    """Test list-users command with custom limit and offset."""
    args = argparse.Namespace(limit=20, offset=10)

    with patch("app.cli.list_users", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = []

        exit_code = await cmd_list_users(args)

    assert exit_code == 0
    mock_list.assert_called_once()
    call_kwargs = mock_list.call_args[1]
    assert call_kwargs["limit"] == 20
    assert call_kwargs["offset"] == 10
