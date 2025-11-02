"""Tests for contacts API endpoints."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from app.core.database import get_db
from app.main import app
from app.models.rate_limit import RateLimitAction, RateLimitLog
from app.models.user import EmailAddress, PhoneNumber, User, VerificationCode, VerificationType
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers.jwt_helpers import MockJWTGenerator
from tests.helpers.test_data import make_unique_email, make_unique_phone


class TestContactsAPI:
    """Test cases for contacts API endpoints."""

    @pytest.fixture
    async def test_user_with_auth(self, db_session: AsyncSession) -> tuple[User, dict[str, str]]:
        """
        Create a test user and matching auth headers.

        Returns:
            Tuple of (User, auth_headers dict)
        """
        # Generate unique external_id
        unique_external_id = f"auth0|test_api_{uuid.uuid4().hex[:8]}"

        # Create user in database
        user = User(external_id=unique_external_id, auth_provider="auth0")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        # Generate JWT for this user
        jwt_token = MockJWTGenerator.generate(auth0_id=unique_external_id)
        auth_headers = {"Authorization": f"Bearer {jwt_token}"}

        return user, auth_headers

    @pytest.fixture(autouse=True)
    async def setup_test(self, db_session: AsyncSession) -> AsyncGenerator[None]:
        """Set up test database dependency override."""

        async def override_get_db() -> AsyncGenerator[AsyncSession]:
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        yield
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_add_email_success(
        self, async_client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession
    ) -> None:
        """Test successfully adding an email address."""
        email = make_unique_email()

        response = await async_client.post(
            "/api/v1/contacts/email",
            json={"email": email},
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["email"] == email
        assert data["verified"] is False
        assert data["is_primary"] is True  # First email is primary

    @pytest.mark.asyncio
    async def test_add_email_duplicate(
        self, async_client: AsyncClient, db_session: AsyncSession, test_user_with_auth: tuple[User, dict[str, str]]
    ) -> None:
        """Test adding duplicate email returns 409."""
        _test_user, auth_headers = test_user_with_auth
        email = make_unique_email()

        # Add email first time
        response1 = await async_client.post(
            "/api/v1/contacts/email",
            json={"email": email},
            headers=auth_headers,
        )
        assert response1.status_code == status.HTTP_201_CREATED

        # Try to add same email again
        response2 = await async_client.post(
            "/api/v1/contacts/email",
            json={"email": email},
            headers=auth_headers,
        )

        assert response2.status_code == status.HTTP_409_CONFLICT
        assert "already registered" in response2.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_add_email_rate_limit(
        self, async_client: AsyncClient, db_session: AsyncSession, test_user_with_auth: tuple[User, dict[str, str]]
    ) -> None:
        """Test rate limiting on failed email additions."""
        test_user, auth_headers = test_user_with_auth

        # Create 5 failed addition attempts
        for i in range(5):
            log_entry = RateLimitLog(
                user_id=test_user.id,
                action_type=RateLimitAction.ADD_CONTACT_FAILURE,
                resource_id=f"test{i}@example.com",
                timestamp=datetime.now(UTC),
            )
            db_session.add(log_entry)
        await db_session.commit()

        # 6th attempt should be rate limited
        response = await async_client.post(
            "/api/v1/contacts/email",
            json={"email": make_unique_email()},
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "Too many failed attempts" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_add_phone_success(
        self, async_client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession
    ) -> None:
        """Test successfully adding a phone number."""
        phone = make_unique_phone()

        response = await async_client.post(
            "/api/v1/contacts/phone",
            json={"phone": phone},
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["phone"] == phone
        assert data["verified"] is False
        assert data["is_primary"] is True  # First phone is primary

    @pytest.mark.asyncio
    async def test_add_phone_duplicate(
        self, async_client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession
    ) -> None:
        """Test adding duplicate phone returns 409."""
        phone = make_unique_phone()

        # Add phone first time
        response1 = await async_client.post(
            "/api/v1/contacts/phone",
            json={"phone": phone},
            headers=auth_headers,
        )
        assert response1.status_code == status.HTTP_201_CREATED

        # Try to add same phone again
        response2 = await async_client.post(
            "/api/v1/contacts/phone",
            json={"phone": phone},
            headers=auth_headers,
        )

        assert response2.status_code == status.HTTP_409_CONFLICT
        assert "already registered" in response2.json()["detail"].lower()

    @pytest.mark.asyncio
    @patch("app.services.verification_service.EmailService.send_verification_email")
    async def test_send_verification_email_success(
        self,
        mock_send_email: AsyncMock,
        async_client: AsyncClient,
        db_session: AsyncSession,
        test_user_with_auth: tuple[User, dict[str, str]],
    ) -> None:
        """Test sending verification code to email."""
        test_user, auth_headers = test_user_with_auth
        mock_send_email.return_value = None

        # Add email first
        email = make_unique_email()
        email_obj = EmailAddress(
            user_id=test_user.id,
            email=email,
            verified=False,
            is_primary=True,
        )
        db_session.add(email_obj)
        await db_session.commit()
        await db_session.refresh(email_obj)

        # Send verification
        response = await async_client.post(
            f"/api/v1/contacts/{email_obj.id}/send-verification",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "email" in data["message"].lower()

        # Verify email was sent
        mock_send_email.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.verification_service.SmsService.send_verification_sms")
    async def test_send_verification_sms_success(
        self,
        mock_send_sms: AsyncMock,
        async_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test sending verification code to phone."""
        mock_send_sms.return_value = None

        # Add phone first
        phone = make_unique_phone()
        phone_obj = PhoneNumber(
            user_id=test_user.id,
            phone=phone,
            verified=False,
            is_primary=True,
        )
        db_session.add(phone_obj)
        await db_session.commit()
        await db_session.refresh(phone_obj)

        # Send verification
        response = await async_client.post(
            f"/api/v1/contacts/{phone_obj.id}/send-verification",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "phone" in data["message"].lower()

        # Verify SMS was sent
        mock_send_sms.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_verification_not_found(self, async_client: AsyncClient, auth_headers: dict[str, str]) -> None:
        """Test sending verification to non-existent contact."""
        fake_id = uuid.uuid4()

        response = await async_client.post(
            f"/api/v1/contacts/{fake_id}/send-verification",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    @patch("app.services.verification_service.EmailService.send_verification_email")
    async def test_send_verification_rate_limit(
        self,
        mock_send_email: AsyncMock,
        async_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test rate limiting on verification code requests."""
        mock_send_email.return_value = None

        # Add email
        email = make_unique_email()
        email_obj = EmailAddress(
            user_id=test_user.id,
            email=email,
            verified=False,
            is_primary=True,
        )
        db_session.add(email_obj)
        await db_session.commit()
        await db_session.refresh(email_obj)

        # Send 3 verification codes (should work)
        for _ in range(3):
            response = await async_client.post(
                f"/api/v1/contacts/{email_obj.id}/send-verification",
                headers=auth_headers,
            )
            assert response.status_code == status.HTTP_200_OK

        # 4th attempt should be rate limited
        response = await async_client.post(
            f"/api/v1/contacts/{email_obj.id}/send-verification",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    @pytest.mark.asyncio
    async def test_verify_code_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test successful code verification."""
        # Add email
        email = make_unique_email()
        email_obj = EmailAddress(
            user_id=test_user.id,
            email=email,
            verified=False,
            is_primary=True,
        )
        db_session.add(email_obj)
        await db_session.commit()
        await db_session.refresh(email_obj)

        # Create verification code
        code = "123456"
        verification_code = VerificationCode(
            user_id=test_user.id,
            code=code,
            type=VerificationType.EMAIL,
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
            used=False,
        )
        db_session.add(verification_code)
        await db_session.commit()

        # Verify code
        response = await async_client.post(
            "/api/v1/contacts/verify",
            json={"contact_id": str(email_obj.id), "code": code},
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True

        # Check email is now verified
        await db_session.refresh(email_obj)
        assert email_obj.verified is True

    @pytest.mark.asyncio
    async def test_verify_code_invalid(
        self, async_client: AsyncClient, auth_headers: dict[str, str], test_user: User
    ) -> None:
        """Test verification with invalid code."""
        response = await async_client.post(
            "/api/v1/contacts/verify",
            json={"contact_id": str(uuid.uuid4()), "code": "999999"},
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_list_contacts_empty(self, async_client: AsyncClient, auth_headers: dict[str, str]) -> None:
        """Test listing contacts when user has none."""
        response = await async_client.get(
            "/api/v1/contacts",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["emails"] == []
        assert data["phones"] == []

    @pytest.mark.asyncio
    async def test_list_contacts_with_data(
        self,
        async_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test listing contacts with emails and phones."""
        # Add email
        email1 = EmailAddress(
            user_id=test_user.id,
            email=make_unique_email(),
            verified=True,
            is_primary=True,
        )
        email2 = EmailAddress(
            user_id=test_user.id,
            email=make_unique_email(),
            verified=False,
            is_primary=False,
        )

        # Add phone
        phone1 = PhoneNumber(
            user_id=test_user.id,
            phone=make_unique_phone(),
            verified=True,
            is_primary=True,
        )

        db_session.add_all([email1, email2, phone1])
        await db_session.commit()

        # List contacts
        response = await async_client.get(
            "/api/v1/contacts",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data["emails"]) == 2
        assert len(data["phones"]) == 1

        # Check primary is first
        assert data["emails"][0]["is_primary"] is True
        assert data["phones"][0]["is_primary"] is True

    @pytest.mark.asyncio
    async def test_delete_contact_email(
        self,
        async_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test deleting an email contact."""
        # Add email
        email = EmailAddress(
            user_id=test_user.id,
            email=make_unique_email(),
            verified=False,
            is_primary=True,
        )
        db_session.add(email)
        await db_session.commit()
        await db_session.refresh(email)

        # Delete email
        response = await async_client.delete(
            f"/api/v1/contacts/{email.id}",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify email is deleted
        result = await db_session.execute(select(EmailAddress).where(EmailAddress.id == email.id))
        deleted_email = result.scalar_one_or_none()
        assert deleted_email is None

    @pytest.mark.asyncio
    async def test_delete_contact_phone(
        self,
        async_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test deleting a phone contact."""
        # Add phone
        phone = PhoneNumber(
            user_id=test_user.id,
            phone=make_unique_phone(),
            verified=False,
            is_primary=True,
        )
        db_session.add(phone)
        await db_session.commit()
        await db_session.refresh(phone)

        # Delete phone
        response = await async_client.delete(
            f"/api/v1/contacts/{phone.id}",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify phone is deleted
        result = await db_session.execute(select(PhoneNumber).where(PhoneNumber.id == phone.id))
        deleted_phone = result.scalar_one_or_none()
        assert deleted_phone is None

    @pytest.mark.asyncio
    async def test_delete_contact_not_found(self, async_client: AsyncClient, auth_headers: dict[str, str]) -> None:
        """Test deleting non-existent contact."""
        fake_id = uuid.uuid4()

        response = await async_client.delete(
            f"/api/v1/contacts/{fake_id}",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_set_primary_email(
        self,
        async_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test setting an email as primary."""
        # Add two emails
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
        await db_session.refresh(email1)
        await db_session.refresh(email2)

        # Set email2 as primary
        response = await async_client.patch(
            f"/api/v1/contacts/{email2.id}/primary",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["is_primary"] is True

        # Verify email1 is no longer primary
        await db_session.refresh(email1)
        assert email1.is_primary is False

        # Verify email2 is now primary
        await db_session.refresh(email2)
        assert email2.is_primary is True

    @pytest.mark.asyncio
    async def test_set_primary_phone(
        self,
        async_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test setting a phone as primary."""
        # Add two phones
        phone1 = PhoneNumber(
            user_id=test_user.id,
            phone=make_unique_phone(),
            verified=True,
            is_primary=True,
        )
        phone2 = PhoneNumber(
            user_id=test_user.id,
            phone=make_unique_phone(),
            verified=True,
            is_primary=False,
        )
        db_session.add_all([phone1, phone2])
        await db_session.commit()
        await db_session.refresh(phone1)
        await db_session.refresh(phone2)

        # Set phone2 as primary
        response = await async_client.patch(
            f"/api/v1/contacts/{phone2.id}/primary",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["is_primary"] is True

        # Verify phone1 is no longer primary
        await db_session.refresh(phone1)
        assert phone1.is_primary is False

        # Verify phone2 is now primary
        await db_session.refresh(phone2)
        assert phone2.is_primary is True

    @pytest.mark.asyncio
    async def test_set_primary_not_found(self, async_client: AsyncClient, auth_headers: dict[str, str]) -> None:
        """Test setting primary for non-existent contact."""
        fake_id = uuid.uuid4()

        response = await async_client.patch(
            f"/api/v1/contacts/{fake_id}/primary",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_contacts_require_authentication(self, async_client: AsyncClient) -> None:
        """Test that all contact endpoints require authentication."""
        endpoints = [
            ("POST", "/api/v1/contacts/email", {"email": "test@example.com"}),
            ("POST", "/api/v1/contacts/phone", {"phone": "+14155552671"}),
            ("POST", f"/api/v1/contacts/{uuid.uuid4()}/send-verification", None),
            ("POST", "/api/v1/contacts/verify", {"contact_id": str(uuid.uuid4()), "code": "123456"}),
            ("GET", "/api/v1/contacts", None),
            ("DELETE", f"/api/v1/contacts/{uuid.uuid4()}", None),
            ("PATCH", f"/api/v1/contacts/{uuid.uuid4()}/primary", None),
        ]

        for method, url, json_data in endpoints:
            if method == "POST":
                response = await async_client.post(url, json=json_data)
            elif method == "GET":
                response = await async_client.get(url)
            elif method == "DELETE":
                response = await async_client.delete(url)
            elif method == "PATCH":
                response = await async_client.patch(url)

            assert response.status_code == status.HTTP_401_UNAUTHORIZED, f"Endpoint {method} {url} should require auth"
