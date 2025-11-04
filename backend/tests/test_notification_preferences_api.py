"""Tests for notification preferences API endpoints."""

import uuid
from collections.abc import AsyncGenerator

import pytest
from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models.notification import NotificationMethod, NotificationPreference
from app.models.route import Route
from app.models.user import EmailAddress, PhoneNumber, User
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers.test_data import make_unique_email, make_unique_phone


class TestNotificationPreferencesAPI:
    """Test cases for notification preferences API endpoints."""

    @pytest.fixture(autouse=True)
    async def setup_test(self, db_session: AsyncSession) -> AsyncGenerator[None]:
        """Set up test database dependency override."""

        async def override_get_db() -> AsyncGenerator[AsyncSession]:
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        yield
        app.dependency_overrides.clear()

    @pytest.fixture
    async def test_route(self, db_session: AsyncSession, test_user: User) -> Route:
        """Create a test route for the test user."""
        route = Route(
            user_id=test_user.id,
            name="Test Commute",
            description="Test route",
            active=True,
        )
        db_session.add(route)
        await db_session.commit()
        await db_session.refresh(route)
        return route

    @pytest.fixture
    async def other_user_route(
        self,
        db_session: AsyncSession,
        another_user: User,
    ) -> Route:
        """Create a test route for another user."""
        route = Route(
            user_id=another_user.id,
            name="Other User Commute",
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
        """Create a verified email for test user."""
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
    async def unverified_email(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> EmailAddress:
        """Create an unverified email for test user."""
        email = EmailAddress(
            user_id=test_user.id,
            email=make_unique_email(),
            verified=False,
            is_primary=False,
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
        """Create a verified phone for test user."""
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

    @pytest.fixture
    async def unverified_phone(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> PhoneNumber:
        """Create an unverified phone for test user."""
        phone = PhoneNumber(
            user_id=test_user.id,
            phone=make_unique_phone(),
            verified=False,
            is_primary=False,
        )
        db_session.add(phone)
        await db_session.commit()
        await db_session.refresh(phone)
        return phone

    @pytest.fixture
    async def other_user_email(
        self,
        db_session: AsyncSession,
        another_user: User,
    ) -> EmailAddress:
        """Create an email for another user."""
        email = EmailAddress(
            user_id=another_user.id,
            email=make_unique_email(),
            verified=True,
            is_primary=True,
        )
        db_session.add(email)
        await db_session.commit()
        await db_session.refresh(email)
        return email

    # ==================== List Preferences Tests ====================

    @pytest.mark.asyncio
    async def test_list_preferences_empty(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_route: Route,
    ) -> None:
        """Test listing preferences when none exist."""
        response = await async_client.get(
            f"/api/v1/routes/{test_route.id}/notifications",
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_preferences_with_data(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_route: Route,
        verified_email: EmailAddress,
        db_session: AsyncSession,
    ) -> None:
        """Test listing preferences with existing preferences."""
        # Create a preference
        pref = NotificationPreference(
            route_id=test_route.id,
            method=NotificationMethod.EMAIL,
            target_email_id=verified_email.id,
        )
        db_session.add(pref)
        await db_session.commit()

        response = await async_client.get(
            f"/api/v1/routes/{test_route.id}/notifications",
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["method"] == "email"
        assert data[0]["target_email_id"] == str(verified_email.id)
        assert data[0]["target_phone_id"] is None

    @pytest.mark.asyncio
    async def test_list_preferences_route_not_found(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
    ) -> None:
        """Test listing preferences for non-existent route."""
        fake_id = uuid.uuid4()
        response = await async_client.get(
            f"/api/v1/routes/{fake_id}/notifications",
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "Route not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_preferences_other_users_route(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        other_user_route: Route,
    ) -> None:
        """Test listing preferences for another user's route."""
        response = await async_client.get(
            f"/api/v1/routes/{other_user_route.id}/notifications",
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_list_preferences_requires_auth(
        self,
        async_client: AsyncClient,
        test_route: Route,
    ) -> None:
        """Test that listing requires authentication."""
        response = await async_client.get(
            f"/api/v1/routes/{test_route.id}/notifications",
        )

        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]

    # ==================== Create Preference Tests ====================

    @pytest.mark.asyncio
    async def test_create_preference_email_success(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_route: Route,
        verified_email: EmailAddress,
    ) -> None:
        """Test successfully creating an email notification preference."""
        response = await async_client.post(
            f"/api/v1/routes/{test_route.id}/notifications",
            json={
                "method": "email",
                "target_email_id": str(verified_email.id),
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["method"] == "email"
        assert data["target_email_id"] == str(verified_email.id)
        assert data["target_phone_id"] is None
        assert data["route_id"] == str(test_route.id)

    @pytest.mark.asyncio
    async def test_create_preference_sms_success(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_route: Route,
        verified_phone: PhoneNumber,
    ) -> None:
        """Test successfully creating an SMS notification preference."""
        response = await async_client.post(
            f"/api/v1/routes/{test_route.id}/notifications",
            json={
                "method": "sms",
                "target_phone_id": str(verified_phone.id),
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["method"] == "sms"
        assert data["target_phone_id"] == str(verified_phone.id)
        assert data["target_email_id"] is None

    @pytest.mark.asyncio
    async def test_create_preference_no_target(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_route: Route,
    ) -> None:
        """Test creating preference without target fails validation."""
        response = await async_client.post(
            f"/api/v1/routes/{test_route.id}/notifications",
            json={
                "method": "email",
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_create_preference_both_targets(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_route: Route,
        verified_email: EmailAddress,
        verified_phone: PhoneNumber,
    ) -> None:
        """Test creating preference with both targets fails validation."""
        response = await async_client.post(
            f"/api/v1/routes/{test_route.id}/notifications",
            json={
                "method": "email",
                "target_email_id": str(verified_email.id),
                "target_phone_id": str(verified_phone.id),
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_create_preference_email_method_requires_email_target(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_route: Route,
        verified_phone: PhoneNumber,
    ) -> None:
        """Test that email method requires email target."""
        response = await async_client.post(
            f"/api/v1/routes/{test_route.id}/notifications",
            json={
                "method": "email",
                "target_phone_id": str(verified_phone.id),
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Email method requires target_email_id" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_preference_sms_method_requires_phone_target(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_route: Route,
        verified_email: EmailAddress,
    ) -> None:
        """Test that SMS method requires phone target."""
        response = await async_client.post(
            f"/api/v1/routes/{test_route.id}/notifications",
            json={
                "method": "sms",
                "target_email_id": str(verified_email.id),
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "SMS method requires target_phone_id" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_preference_unverified_email(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_route: Route,
        unverified_email: EmailAddress,
    ) -> None:
        """Test creating preference with unverified email fails."""
        response = await async_client.post(
            f"/api/v1/routes/{test_route.id}/notifications",
            json={
                "method": "email",
                "target_email_id": str(unverified_email.id),
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "must be verified" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_preference_unverified_phone(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_route: Route,
        unverified_phone: PhoneNumber,
    ) -> None:
        """Test creating preference with unverified phone fails."""
        response = await async_client.post(
            f"/api/v1/routes/{test_route.id}/notifications",
            json={
                "method": "sms",
                "target_phone_id": str(unverified_phone.id),
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "must be verified" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_preference_email_not_found(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_route: Route,
    ) -> None:
        """Test creating preference with non-existent email."""
        fake_id = uuid.uuid4()
        response = await async_client.post(
            f"/api/v1/routes/{test_route.id}/notifications",
            json={
                "method": "email",
                "target_email_id": str(fake_id),
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "Email address not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_preference_phone_not_found(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_route: Route,
    ) -> None:
        """Test creating preference with non-existent phone."""
        fake_id = uuid.uuid4()
        response = await async_client.post(
            f"/api/v1/routes/{test_route.id}/notifications",
            json={
                "method": "sms",
                "target_phone_id": str(fake_id),
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "Phone number not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_preference_other_users_email(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_route: Route,
        other_user_email: EmailAddress,
    ) -> None:
        """Test creating preference with another user's email fails."""
        response = await async_client.post(
            f"/api/v1/routes/{test_route.id}/notifications",
            json={
                "method": "email",
                "target_email_id": str(other_user_email.id),
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_create_preference_duplicate(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_route: Route,
        verified_email: EmailAddress,
        db_session: AsyncSession,
    ) -> None:
        """Test creating duplicate preference fails."""
        # Create first preference
        pref = NotificationPreference(
            route_id=test_route.id,
            method=NotificationMethod.EMAIL,
            target_email_id=verified_email.id,
        )
        db_session.add(pref)
        await db_session.commit()

        # Attempt to create duplicate
        response = await async_client.post(
            f"/api/v1/routes/{test_route.id}/notifications",
            json={
                "method": "email",
                "target_email_id": str(verified_email.id),
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "already exists" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_preference_max_limit(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_route: Route,
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test creating preference fails when limit is reached."""
        # Create max number of preferences
        for i in range(settings.MAX_NOTIFICATION_PREFERENCES_PER_ROUTE):
            email = EmailAddress(
                user_id=test_user.id,
                email=make_unique_email(),
                verified=True,
                is_primary=i == 0,
            )
            db_session.add(email)
            await db_session.flush()

            pref = NotificationPreference(
                route_id=test_route.id,
                method=NotificationMethod.EMAIL,
                target_email_id=email.id,
            )
            db_session.add(pref)

        await db_session.commit()

        # Create one more email for the attempt
        extra_email = EmailAddress(
            user_id=test_user.id,
            email=make_unique_email(),
            verified=True,
            is_primary=False,
        )
        db_session.add(extra_email)
        await db_session.commit()
        await db_session.refresh(extra_email)

        # Attempt to create one more preference
        response = await async_client.post(
            f"/api/v1/routes/{test_route.id}/notifications",
            json={
                "method": "email",
                "target_email_id": str(extra_email.id),
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Maximum" in response.json()["detail"]
        assert str(settings.MAX_NOTIFICATION_PREFERENCES_PER_ROUTE) in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_preference_route_not_found(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        verified_email: EmailAddress,
    ) -> None:
        """Test creating preference for non-existent route."""
        fake_id = uuid.uuid4()
        response = await async_client.post(
            f"/api/v1/routes/{fake_id}/notifications",
            json={
                "method": "email",
                "target_email_id": str(verified_email.id),
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "Route not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_preference_requires_auth(
        self,
        async_client: AsyncClient,
        test_route: Route,
        verified_email: EmailAddress,
    ) -> None:
        """Test that creating preference requires authentication."""
        response = await async_client.post(
            f"/api/v1/routes/{test_route.id}/notifications",
            json={
                "method": "email",
                "target_email_id": str(verified_email.id),
            },
        )

        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]

    # ==================== Update Preference Tests ====================

    @pytest.mark.asyncio
    async def test_update_preference_change_method(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_route: Route,
        verified_phone: PhoneNumber,
        db_session: AsyncSession,
    ) -> None:
        """Test updating preference method."""
        # Create preference with SMS
        pref = NotificationPreference(
            route_id=test_route.id,
            method=NotificationMethod.SMS,
            target_phone_id=verified_phone.id,
        )
        db_session.add(pref)
        await db_session.commit()
        await db_session.refresh(pref)

        # Update to EMAIL (but this should fail because phone is set)
        # So let's just change the phone target
        another_phone = PhoneNumber(
            user_id=test_route.user_id,
            phone=make_unique_phone(),
            verified=True,
            is_primary=False,
        )
        db_session.add(another_phone)
        await db_session.commit()
        await db_session.refresh(another_phone)

        response = await async_client.patch(
            f"/api/v1/routes/{test_route.id}/notifications/{pref.id}",
            json={
                "target_phone_id": str(another_phone.id),
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["target_phone_id"] == str(another_phone.id)

    @pytest.mark.asyncio
    async def test_update_preference_change_target(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_route: Route,
        verified_email: EmailAddress,
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test updating preference target."""
        # Create preference
        pref = NotificationPreference(
            route_id=test_route.id,
            method=NotificationMethod.EMAIL,
            target_email_id=verified_email.id,
        )
        db_session.add(pref)
        await db_session.commit()
        await db_session.refresh(pref)

        # Create another email
        another_email = EmailAddress(
            user_id=test_user.id,
            email=make_unique_email(),
            verified=True,
            is_primary=False,
        )
        db_session.add(another_email)
        await db_session.commit()
        await db_session.refresh(another_email)

        # Update target
        response = await async_client.patch(
            f"/api/v1/routes/{test_route.id}/notifications/{pref.id}",
            json={
                "target_email_id": str(another_email.id),
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["target_email_id"] == str(another_email.id)

    @pytest.mark.asyncio
    async def test_update_preference_both_targets_fails(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_route: Route,
        verified_email: EmailAddress,
        verified_phone: PhoneNumber,
        db_session: AsyncSession,
    ) -> None:
        """Test updating preference with both targets fails."""
        # Create preference
        pref = NotificationPreference(
            route_id=test_route.id,
            method=NotificationMethod.EMAIL,
            target_email_id=verified_email.id,
        )
        db_session.add(pref)
        await db_session.commit()
        await db_session.refresh(pref)

        # Try to set both targets
        response = await async_client.patch(
            f"/api/v1/routes/{test_route.id}/notifications/{pref.id}",
            json={
                "target_email_id": str(verified_email.id),
                "target_phone_id": str(verified_phone.id),
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_update_preference_switch_from_email_to_sms(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_route: Route,
        verified_email: EmailAddress,
        verified_phone: PhoneNumber,
        db_session: AsyncSession,
    ) -> None:
        """Test switching from email to SMS notification."""
        # Create email preference
        pref = NotificationPreference(
            route_id=test_route.id,
            method=NotificationMethod.EMAIL,
            target_email_id=verified_email.id,
        )
        db_session.add(pref)
        await db_session.commit()
        await db_session.refresh(pref)

        # Switch to SMS
        response = await async_client.patch(
            f"/api/v1/routes/{test_route.id}/notifications/{pref.id}",
            json={
                "method": "sms",
                "target_phone_id": str(verified_phone.id),
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["method"] == "sms"
        assert data["target_phone_id"] == str(verified_phone.id)
        assert data["target_email_id"] is None

    @pytest.mark.asyncio
    async def test_update_preference_unverified_email(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_route: Route,
        verified_email: EmailAddress,
        unverified_email: EmailAddress,
        db_session: AsyncSession,
    ) -> None:
        """Test updating to unverified email fails."""
        # Create preference
        pref = NotificationPreference(
            route_id=test_route.id,
            method=NotificationMethod.EMAIL,
            target_email_id=verified_email.id,
        )
        db_session.add(pref)
        await db_session.commit()
        await db_session.refresh(pref)

        # Try to update to unverified email
        response = await async_client.patch(
            f"/api/v1/routes/{test_route.id}/notifications/{pref.id}",
            json={
                "target_email_id": str(unverified_email.id),
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "must be verified" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_update_preference_to_duplicate(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_route: Route,
        test_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Test updating preference to create duplicate fails."""
        # Create two emails
        email1 = EmailAddress(
            user_id=test_user.id,
            email=make_unique_email(),
            verified=True,
            is_primary=True,
        )
        email2 = EmailAddress(
            user_id=test_user.id,
            email=make_unique_email(),
            verified=True,
            is_primary=False,
        )
        db_session.add_all([email1, email2])
        await db_session.commit()

        # Create two preferences
        pref1 = NotificationPreference(
            route_id=test_route.id,
            method=NotificationMethod.EMAIL,
            target_email_id=email1.id,
        )
        pref2 = NotificationPreference(
            route_id=test_route.id,
            method=NotificationMethod.EMAIL,
            target_email_id=email2.id,
        )
        db_session.add_all([pref1, pref2])
        await db_session.commit()
        await db_session.refresh(pref2)

        # Try to update pref2 to use email1 (duplicate)
        response = await async_client.patch(
            f"/api/v1/routes/{test_route.id}/notifications/{pref2.id}",
            json={
                "target_email_id": str(email1.id),
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "already exists" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_update_preference_not_found(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_route: Route,
        verified_email: EmailAddress,
    ) -> None:
        """Test updating non-existent preference."""
        fake_id = uuid.uuid4()
        response = await async_client.patch(
            f"/api/v1/routes/{test_route.id}/notifications/{fake_id}",
            json={
                "target_email_id": str(verified_email.id),
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_update_preference_other_users_preference(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        other_user_route: Route,
        other_user_email: EmailAddress,
        db_session: AsyncSession,
    ) -> None:
        """Test updating another user's preference fails."""
        # Create preference for other user
        pref = NotificationPreference(
            route_id=other_user_route.id,
            method=NotificationMethod.EMAIL,
            target_email_id=other_user_email.id,
        )
        db_session.add(pref)
        await db_session.commit()
        await db_session.refresh(pref)

        # Try to update it
        response = await async_client.patch(
            f"/api/v1/routes/{other_user_route.id}/notifications/{pref.id}",
            json={
                "method": "sms",
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_update_preference_requires_auth(
        self,
        async_client: AsyncClient,
        test_route: Route,
        verified_email: EmailAddress,
        db_session: AsyncSession,
    ) -> None:
        """Test that updating requires authentication."""
        # Create preference
        pref = NotificationPreference(
            route_id=test_route.id,
            method=NotificationMethod.EMAIL,
            target_email_id=verified_email.id,
        )
        db_session.add(pref)
        await db_session.commit()
        await db_session.refresh(pref)

        response = await async_client.patch(
            f"/api/v1/routes/{test_route.id}/notifications/{pref.id}",
            json={
                "method": "sms",
            },
        )

        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]

    @pytest.mark.asyncio
    async def test_update_preference_email_method_mismatch(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_route: Route,
        verified_phone: PhoneNumber,
        db_session: AsyncSession,
    ) -> None:
        """Test updating to email method with phone target fails."""
        # Create SMS preference
        pref = NotificationPreference(
            route_id=test_route.id,
            method=NotificationMethod.SMS,
            target_phone_id=verified_phone.id,
        )
        db_session.add(pref)
        await db_session.commit()
        await db_session.refresh(pref)

        # Try to change method to email without changing target
        response = await async_client.patch(
            f"/api/v1/routes/{test_route.id}/notifications/{pref.id}",
            json={
                "method": "email",
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Email method requires target_email_id" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_update_preference_sms_method_mismatch(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_route: Route,
        verified_email: EmailAddress,
        db_session: AsyncSession,
    ) -> None:
        """Test updating to SMS method with email target fails."""
        # Create email preference
        pref = NotificationPreference(
            route_id=test_route.id,
            method=NotificationMethod.EMAIL,
            target_email_id=verified_email.id,
        )
        db_session.add(pref)
        await db_session.commit()
        await db_session.refresh(pref)

        # Try to change method to SMS without changing target
        response = await async_client.patch(
            f"/api/v1/routes/{test_route.id}/notifications/{pref.id}",
            json={
                "method": "sms",
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "SMS method requires target_phone_id" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_update_preference_unverified_phone(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_route: Route,
        verified_phone: PhoneNumber,
        unverified_phone: PhoneNumber,
        db_session: AsyncSession,
    ) -> None:
        """Test updating to unverified phone fails."""
        # Create SMS preference
        pref = NotificationPreference(
            route_id=test_route.id,
            method=NotificationMethod.SMS,
            target_phone_id=verified_phone.id,
        )
        db_session.add(pref)
        await db_session.commit()
        await db_session.refresh(pref)

        # Try to update to unverified phone
        response = await async_client.patch(
            f"/api/v1/routes/{test_route.id}/notifications/{pref.id}",
            json={
                "target_phone_id": str(unverified_phone.id),
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "must be verified" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_update_preference_phone_not_found(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_route: Route,
        verified_phone: PhoneNumber,
        db_session: AsyncSession,
    ) -> None:
        """Test updating to non-existent phone."""
        # Create preference
        pref = NotificationPreference(
            route_id=test_route.id,
            method=NotificationMethod.SMS,
            target_phone_id=verified_phone.id,
        )
        db_session.add(pref)
        await db_session.commit()
        await db_session.refresh(pref)

        fake_id = uuid.uuid4()
        response = await async_client.patch(
            f"/api/v1/routes/{test_route.id}/notifications/{pref.id}",
            json={
                "target_phone_id": str(fake_id),
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_update_preference_contact_not_found(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_route: Route,
        verified_email: EmailAddress,
        db_session: AsyncSession,
    ) -> None:
        """Test updating to non-existent contact."""
        # Create preference
        pref = NotificationPreference(
            route_id=test_route.id,
            method=NotificationMethod.EMAIL,
            target_email_id=verified_email.id,
        )
        db_session.add(pref)
        await db_session.commit()
        await db_session.refresh(pref)

        fake_id = uuid.uuid4()
        response = await async_client.patch(
            f"/api/v1/routes/{test_route.id}/notifications/{pref.id}",
            json={
                "target_email_id": str(fake_id),
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    # ==================== Delete Preference Tests ====================

    @pytest.mark.asyncio
    async def test_delete_preference_success(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_route: Route,
        verified_email: EmailAddress,
        db_session: AsyncSession,
    ) -> None:
        """Test successfully deleting a preference."""
        # Create preference
        pref = NotificationPreference(
            route_id=test_route.id,
            method=NotificationMethod.EMAIL,
            target_email_id=verified_email.id,
        )
        db_session.add(pref)
        await db_session.commit()
        await db_session.refresh(pref)

        response = await async_client.delete(
            f"/api/v1/routes/{test_route.id}/notifications/{pref.id}",
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify deletion
        list_response = await async_client.get(
            f"/api/v1/routes/{test_route.id}/notifications",
            headers=auth_headers_for_user,
        )
        assert list_response.json() == []

    @pytest.mark.asyncio
    async def test_delete_preference_not_found(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_route: Route,
    ) -> None:
        """Test deleting non-existent preference."""
        fake_id = uuid.uuid4()
        response = await async_client.delete(
            f"/api/v1/routes/{test_route.id}/notifications/{fake_id}",
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_preference_other_users_preference(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        other_user_route: Route,
        other_user_email: EmailAddress,
        db_session: AsyncSession,
    ) -> None:
        """Test deleting another user's preference fails."""
        # Create preference for other user
        pref = NotificationPreference(
            route_id=other_user_route.id,
            method=NotificationMethod.EMAIL,
            target_email_id=other_user_email.id,
        )
        db_session.add(pref)
        await db_session.commit()
        await db_session.refresh(pref)

        response = await async_client.delete(
            f"/api/v1/routes/{other_user_route.id}/notifications/{pref.id}",
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_preference_requires_auth(
        self,
        async_client: AsyncClient,
        test_route: Route,
        verified_email: EmailAddress,
        db_session: AsyncSession,
    ) -> None:
        """Test that deleting requires authentication."""
        # Create preference
        pref = NotificationPreference(
            route_id=test_route.id,
            method=NotificationMethod.EMAIL,
            target_email_id=verified_email.id,
        )
        db_session.add(pref)
        await db_session.commit()
        await db_session.refresh(pref)

        response = await async_client.delete(
            f"/api/v1/routes/{test_route.id}/notifications/{pref.id}",
        )

        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]

    @pytest.mark.asyncio
    async def test_update_preference_route_mismatch(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        verified_email: EmailAddress,
        db_session: AsyncSession,
    ) -> None:
        """Test updating with mismatched route_id in URL."""
        # Create two routes
        route1 = Route(user_id=test_user.id, name="Route 1", active=True)
        route2 = Route(user_id=test_user.id, name="Route 2", active=True)
        db_session.add_all([route1, route2])
        await db_session.commit()
        await db_session.refresh(route1)
        await db_session.refresh(route2)

        # Create preference for route1
        pref = NotificationPreference(
            route_id=route1.id,
            method=NotificationMethod.EMAIL,
            target_email_id=verified_email.id,
        )
        db_session.add(pref)
        await db_session.commit()
        await db_session.refresh(pref)

        # Try to update with route2's ID in URL
        response = await async_client.patch(
            f"/api/v1/routes/{route2.id}/notifications/{pref.id}",
            json={
                "method": "email",
            },
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "does not match" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_delete_preference_route_mismatch(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        test_user: User,
        verified_email: EmailAddress,
        db_session: AsyncSession,
    ) -> None:
        """Test deleting with mismatched route_id in URL."""
        # Create two routes
        route1 = Route(user_id=test_user.id, name="Route 1", active=True)
        route2 = Route(user_id=test_user.id, name="Route 2", active=True)
        db_session.add_all([route1, route2])
        await db_session.commit()
        await db_session.refresh(route1)
        await db_session.refresh(route2)

        # Create preference for route1
        pref = NotificationPreference(
            route_id=route1.id,
            method=NotificationMethod.EMAIL,
            target_email_id=verified_email.id,
        )
        db_session.add(pref)
        await db_session.commit()
        await db_session.refresh(pref)

        # Try to delete with route2's ID in URL
        response = await async_client.delete(
            f"/api/v1/routes/{route2.id}/notifications/{pref.id}",
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "does not match" in response.json()["detail"].lower()
