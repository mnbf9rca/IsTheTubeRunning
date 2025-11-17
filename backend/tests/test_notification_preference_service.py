"""Direct service-level tests for notification preference service."""

import pytest
from app.models.notification import NotificationMethod
from app.models.route import UserRoute
from app.models.user import EmailAddress, PhoneNumber, User
from app.services.notification_preference_service import NotificationPreferenceService
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers.test_data import make_unique_email, make_unique_phone


class TestNotificationPreferenceServiceDirect:
    """Test cases for service-level validation bypassing Pydantic."""

    @pytest.fixture
    async def test_route(self, db_session: AsyncSession, test_user: User) -> UserRoute:
        """Create a test route."""
        route = UserRoute(
            user_id=test_user.id,
            name="Test Route",
            active=True,
        )
        db_session.add(route)
        await db_session.commit()
        await db_session.refresh(route)
        return route

    @pytest.fixture
    async def verified_email(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> EmailAddress:
        """Create a verified email."""
        email = EmailAddress(
            user_id=test_user.id,
            email=make_unique_email(),
            verified=True,
            is_primary=True,
        )
        db_session.add(email)
        await db_session.commit()
        await db_session.refresh(email)
        return email

    @pytest.fixture
    async def verified_phone(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> PhoneNumber:
        """Create a verified phone."""
        phone = PhoneNumber(
            user_id=test_user.id,
            phone=make_unique_phone(),
            verified=True,
            is_primary=True,
        )
        db_session.add(phone)
        await db_session.commit()
        await db_session.refresh(phone)
        return phone

    @pytest.mark.asyncio
    async def test_create_preference_no_targets_direct(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_route: UserRoute,
    ) -> None:
        """Test creating preference with no targets (bypassing Pydantic)."""
        service = NotificationPreferenceService(db_session)

        with pytest.raises(HTTPException) as exc_info:
            await service.create_preference(
                route_id=test_route.id,
                user_id=test_user.id,
                method=NotificationMethod.EMAIL,
                target_email_id=None,
                target_phone_id=None,
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Exactly one" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_update_preference_both_targets_direct(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_route: UserRoute,
        verified_email: EmailAddress,
        verified_phone: PhoneNumber,
    ) -> None:
        """Test updating preference with both targets (bypassing Pydantic)."""
        service = NotificationPreferenceService(db_session)

        # Create initial preference
        pref = await service.create_preference(
            route_id=test_route.id,
            user_id=test_user.id,
            method=NotificationMethod.EMAIL,
            target_email_id=verified_email.id,
            target_phone_id=None,
        )

        # Try to update with both targets
        with pytest.raises(HTTPException) as exc_info:
            await service.update_preference(
                preference_id=pref.id,
                user_id=test_user.id,
                method=None,
                target_email_id=verified_email.id,
                target_phone_id=verified_phone.id,
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "both" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_update_preference_method_change_without_target(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_route: UserRoute,
        verified_email: EmailAddress,
    ) -> None:
        """Test changing method without providing matching target."""
        service = NotificationPreferenceService(db_session)

        # Create initial preference with email
        pref = await service.create_preference(
            route_id=test_route.id,
            user_id=test_user.id,
            method=NotificationMethod.EMAIL,
            target_email_id=verified_email.id,
            target_phone_id=None,
        )

        # Try to change method to SMS without providing phone target
        # This leaves email set but method as SMS, which is invalid
        with pytest.raises(HTTPException) as exc_info:
            await service.update_preference(
                preference_id=pref.id,
                user_id=test_user.id,
                method=NotificationMethod.SMS,
                target_email_id=None,
                target_phone_id=None,
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "SMS method requires target_phone_id" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_update_preference_email_method_change_without_target(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_route: UserRoute,
        verified_phone: PhoneNumber,
    ) -> None:
        """Test changing from SMS to EMAIL method without providing email target."""
        service = NotificationPreferenceService(db_session)

        # Create initial preference with phone
        pref = await service.create_preference(
            route_id=test_route.id,
            user_id=test_user.id,
            method=NotificationMethod.SMS,
            target_email_id=None,
            target_phone_id=verified_phone.id,
        )

        # Try to change method to EMAIL without providing email target
        # This leaves phone set but method as EMAIL, which is invalid
        with pytest.raises(HTTPException) as exc_info:
            await service.update_preference(
                preference_id=pref.id,
                user_id=test_user.id,
                method=NotificationMethod.EMAIL,
                target_email_id=None,
                target_phone_id=None,
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Email method requires target_email_id" in exc_info.value.detail
