"""Unit tests for admin helper functions."""

from uuid import uuid4

import pytest
from app.core.admin import check_is_admin, get_admin_user, require_admin
from app.models.admin import AdminUser
from app.models.user import User
from app.services.auth_service import AuthService
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers.test_data import make_unique_external_id


class TestGetAdminUser:
    """Test get_admin_user helper function."""

    @pytest.mark.asyncio
    async def test_returns_admin_user_when_exists(
        self, db_session: AsyncSession, admin_user: tuple[User, AdminUser]
    ) -> None:
        """Should return AdminUser record for admin users."""
        test_user, expected_admin_user = admin_user

        result = await get_admin_user(test_user.id, db_session)

        assert result is not None
        assert result.user_id == test_user.id
        assert result.role == expected_admin_user.role
        assert result.granted_at == expected_admin_user.granted_at

    @pytest.mark.asyncio
    async def test_returns_none_when_not_admin(self, db_session: AsyncSession, test_user: User) -> None:
        """Should return None for non-admin users."""
        result = await get_admin_user(test_user.id, db_session)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_nonexistent_user(self, db_session: AsyncSession) -> None:
        """Should return None for non-existent user IDs."""
        fake_id = uuid4()
        result = await get_admin_user(fake_id, db_session)
        assert result is None


class TestCheckIsAdmin:
    """Test check_is_admin helper function."""

    @pytest.mark.asyncio
    async def test_returns_true_for_admin_users(
        self, db_session: AsyncSession, admin_user: tuple[User, AdminUser]
    ) -> None:
        """Should return True when user is admin."""
        test_user, _ = admin_user

        is_admin = await check_is_admin(test_user.id, db_session)

        assert is_admin is True

    @pytest.mark.asyncio
    async def test_returns_false_for_non_admin_users(self, db_session: AsyncSession, test_user: User) -> None:
        """Should return False when user is not admin."""
        is_admin = await check_is_admin(test_user.id, db_session)
        assert is_admin is False

    @pytest.mark.asyncio
    async def test_returns_false_for_nonexistent_user(self, db_session: AsyncSession) -> None:
        """Should return False for non-existent user IDs."""
        fake_id = uuid4()
        is_admin = await check_is_admin(fake_id, db_session)
        assert is_admin is False


class TestRequireAdmin:
    """Test require_admin dependency (verify refactoring maintains behavior)."""

    @pytest.mark.asyncio
    async def test_returns_admin_user_for_admin(
        self, db_session: AsyncSession, admin_user: tuple[User, AdminUser]
    ) -> None:
        """Should return AdminUser record when user is admin."""
        test_user, expected_admin_user = admin_user

        result = await require_admin(current_user=test_user, db=db_session)

        assert result is not None
        assert result.user_id == test_user.id
        assert result.role == expected_admin_user.role

    @pytest.mark.asyncio
    async def test_raises_403_for_non_admin(self, db_session: AsyncSession, test_user: User) -> None:
        """Should raise 403 HTTPException for non-admin users."""
        with pytest.raises(HTTPException) as exc_info:
            await require_admin(current_user=test_user, db=db_session)

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Admin privileges required"

    @pytest.mark.asyncio
    async def test_raises_403_for_nonexistent_user(self, db_session: AsyncSession) -> None:
        """Should raise 403 for user not in admin_users table."""
        # Create a user without admin privileges

        auth_service = AuthService(db_session)
        external_id = make_unique_external_id("auth0|non_admin")
        non_admin_user = await auth_service.create_user(external_id=external_id, auth_provider="auth0")

        with pytest.raises(HTTPException) as exc_info:
            await require_admin(current_user=non_admin_user, db=db_session)

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Admin privileges required"
