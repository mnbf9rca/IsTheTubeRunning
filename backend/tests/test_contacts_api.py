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

from tests.helpers.test_data import make_unique_email, make_unique_phone


class TestContactsAPI:
    """Test cases for contacts API endpoints."""

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
    async def test_add_email_duplicate(self, fresh_async_client: AsyncClient, auth_headers: dict[str, str]) -> None:
        """Test adding duplicate email returns 409."""
        email = make_unique_email()

        response1 = await fresh_async_client.post("/api/v1/contacts/email", json={"email": email}, headers=auth_headers)
        assert response1.status_code == status.HTTP_201_CREATED

        response2 = await fresh_async_client.post("/api/v1/contacts/email", json={"email": email}, headers=auth_headers)
        assert response2.status_code == status.HTTP_409_CONFLICT
        assert "already registered" in response2.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_add_email_rate_limit(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        auth_headers_for_user: dict[str, str],
        test_user: User,
    ) -> None:
        """Test rate limiting on failed email additions."""

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
            headers=auth_headers_for_user,
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
    async def test_add_phone_duplicate(self, fresh_async_client: AsyncClient, auth_headers: dict[str, str]) -> None:
        """Test adding duplicate phone returns 409."""
        phone = make_unique_phone()

        response1 = await fresh_async_client.post("/api/v1/contacts/phone", json={"phone": phone}, headers=auth_headers)
        assert response1.status_code == status.HTTP_201_CREATED

        response2 = await fresh_async_client.post("/api/v1/contacts/phone", json={"phone": phone}, headers=auth_headers)
        assert response2.status_code == status.HTTP_409_CONFLICT
        assert "already registered" in response2.json()["detail"].lower()

    @pytest.mark.asyncio
    @patch("app.services.verification_service.EmailService.send_verification_email")
    async def test_send_verification_email_success(
        self,
        mock_send_email: AsyncMock,
        async_client: AsyncClient,
        db_session: AsyncSession,
        auth_headers_for_user: dict[str, str],
        test_user: User,
    ) -> None:
        """Test sending verification code to email."""
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
            headers=auth_headers_for_user,
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
        db_session: AsyncSession,
        auth_headers_for_user: dict[str, str],
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
            headers=auth_headers_for_user,
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
        db_session: AsyncSession,
        auth_headers_for_user: dict[str, str],
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
                headers=auth_headers_for_user,
            )
            assert response.status_code == status.HTTP_200_OK

        # 4th attempt should be rate limited
        response = await async_client.post(
            f"/api/v1/contacts/{email_obj.id}/send-verification",
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    @pytest.mark.asyncio
    async def test_verify_code_success(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        auth_headers_for_user: dict[str, str],
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
            contact_id=email_obj.id,
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
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True

        # Check email is now verified
        await db_session.refresh(email_obj)
        assert email_obj.verified is True

    @pytest.mark.asyncio
    async def test_verify_code_invalid(self, async_client: AsyncClient, auth_headers: dict[str, str]) -> None:
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
        db_session: AsyncSession,
        auth_headers_for_user: dict[str, str],
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
            headers=auth_headers_for_user,
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
        db_session: AsyncSession,
        auth_headers_for_user: dict[str, str],
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
            headers=auth_headers_for_user,
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
        db_session: AsyncSession,
        auth_headers_for_user: dict[str, str],
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
            headers=auth_headers_for_user,
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
        db_session: AsyncSession,
        auth_headers_for_user: dict[str, str],
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
            headers=auth_headers_for_user,
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
        auth_headers_for_user: dict[str, str],
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
            headers=auth_headers_for_user,
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
    async def test_set_primary_email_when_no_current_primary(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        auth_headers_for_user: dict[str, str],
        test_user: User,
    ) -> None:
        """Test setting an email as primary when no email is currently primary."""
        # Add email with is_primary=False
        email = EmailAddress(
            user_id=test_user.id,
            email=make_unique_email(),
            verified=True,
            is_primary=False,
        )
        db_session.add(email)
        await db_session.commit()
        await db_session.refresh(email)

        # Set email as primary (no current primary exists)
        response = await async_client.patch(
            f"/api/v1/contacts/{email.id}/primary",
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["is_primary"] is True

        # Verify email is now primary
        await db_session.refresh(email)
        assert email.is_primary is True

    @pytest.mark.asyncio
    async def test_set_primary_phone_when_no_current_primary(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        auth_headers_for_user: dict[str, str],
        test_user: User,
    ) -> None:
        """Test setting a phone as primary when no phone is currently primary."""
        # Add phone with is_primary=False
        phone = PhoneNumber(
            user_id=test_user.id,
            phone=make_unique_phone(),
            verified=True,
            is_primary=False,
        )
        db_session.add(phone)
        await db_session.commit()
        await db_session.refresh(phone)

        # Set phone as primary (no current primary exists)
        response = await async_client.patch(
            f"/api/v1/contacts/{phone.id}/primary",
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["is_primary"] is True

        # Verify phone is now primary
        await db_session.refresh(phone)
        assert phone.is_primary is True

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

            # FastAPI returns 403 Forbidden for missing credentials, 401 for invalid credentials
            assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN], (
                f"Endpoint {method} {url} should require auth"
            )

    # ==================== Additional Test Cases from Code Review ====================

    @pytest.mark.asyncio
    async def test_add_email_invalid_format(
        self, async_client: AsyncClient, auth_headers_for_user: dict[str, str]
    ) -> None:
        """Test adding email with invalid format (validates email-validator library)."""
        invalid_email = "not-an-email"  # Missing @

        response = await async_client.post(
            "/api/v1/contacts/email",
            json={"email": invalid_email},
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_add_phone_invalid_format(
        self, async_client: AsyncClient, auth_headers_for_user: dict[str, str]
    ) -> None:
        """Test adding phone with invalid format (validates phonenumbers library)."""
        invalid_phone = "123"  # Too short

        response = await async_client.post(
            "/api/v1/contacts/phone",
            json={"phone": invalid_phone},
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_add_phone_invalid_format_with_error_detail(
        self, async_client: AsyncClient, auth_headers_for_user: dict[str, str]
    ) -> None:
        """Test adding phone with invalid format returns detailed error message."""
        # Test various invalid phone formats to ensure NumberParseException is raised
        invalid_phones = [
            "abc",  # Letters
            "+++123",  # Too many plus signs
            "",  # Empty string
        ]

        for invalid_phone in invalid_phones:
            response = await async_client.post(
                "/api/v1/contacts/phone",
                json={"phone": invalid_phone},
                headers=auth_headers_for_user,
            )

            assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
            # Verify error detail exists (validates lines 70-71)
            error_data = response.json()
            assert "detail" in error_data

    @pytest.mark.asyncio
    async def test_add_email_duplicate_casing(
        self, fresh_async_client: AsyncClient, auth_headers_for_user: dict[str, str]
    ) -> None:
        """Test adding duplicate email with different casing returns 409."""
        email_lower = make_unique_email().lower()
        email_mixed = email_lower[0].upper() + email_lower[1:]

        response1 = await fresh_async_client.post(
            "/api/v1/contacts/email", json={"email": email_lower}, headers=auth_headers_for_user
        )
        assert response1.status_code == status.HTTP_201_CREATED

        response2 = await fresh_async_client.post(
            "/api/v1/contacts/email", json={"email": email_mixed}, headers=auth_headers_for_user
        )
        assert response2.status_code == status.HTTP_409_CONFLICT
        assert "already registered" in response2.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_add_phone_duplicate_formatting(
        self, fresh_async_client: AsyncClient, auth_headers_for_user: dict[str, str]
    ) -> None:
        """Test adding phone with different formatting is recognized as duplicate."""
        phone_formatted = "+1 202-555-1234"
        phone_plain = "+12025551234"

        response1 = await fresh_async_client.post(
            "/api/v1/contacts/phone", json={"phone": phone_formatted}, headers=auth_headers_for_user
        )
        assert response1.status_code == status.HTTP_201_CREATED

        response2 = await fresh_async_client.post(
            "/api/v1/contacts/phone", json={"phone": phone_plain}, headers=auth_headers_for_user
        )
        assert response2.status_code == status.HTTP_409_CONFLICT
        assert "already registered" in response2.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_set_primary_unverified_contact(
        self, async_client: AsyncClient, auth_headers_for_user: dict[str, str], db_session: AsyncSession
    ) -> None:
        """Test setting unverified contact as primary fails."""
        email = make_unique_email()

        # Add unverified email
        response = await async_client.post(
            "/api/v1/contacts/email",
            json={"email": email},
            headers=auth_headers_for_user,
        )
        assert response.status_code == status.HTTP_201_CREATED
        contact_id = response.json()["id"]

        # Try to set as primary (should fail - not verified)
        response = await async_client.patch(
            f"/api/v1/contacts/{contact_id}/primary",
            headers=auth_headers_for_user,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "verified" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_delete_primary_contact(
        self, async_client: AsyncClient, auth_headers_for_user: dict[str, str], db_session: AsyncSession
    ) -> None:
        """Test deleting the primary email contact."""
        email = make_unique_email()

        # Add and verify email (will be primary as first email)
        add_response = await async_client.post(
            "/api/v1/contacts/email",
            json={"email": email},
            headers=auth_headers_for_user,
        )
        assert add_response.status_code == status.HTTP_201_CREATED
        contact_id = add_response.json()["id"]
        assert add_response.json()["is_primary"] is True

        # Delete the primary contact
        delete_response = await async_client.delete(
            f"/api/v1/contacts/{contact_id}",
            headers=auth_headers_for_user,
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT

        # Verify contact is deleted
        list_response = await async_client.get(
            "/api/v1/contacts",
            headers=auth_headers_for_user,
        )
        assert list_response.status_code == status.HTTP_200_OK
        assert len(list_response.json()["emails"]) == 0

    @pytest.mark.asyncio
    async def test_verify_code_wrong_contact_id(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test verifying code with wrong contact_id fails."""
        email1 = make_unique_email()
        email2 = make_unique_email()

        # Add two emails
        response1 = await async_client.post(
            "/api/v1/contacts/email",
            json={"email": email1},
            headers=auth_headers_for_user,
        )
        contact1_id = response1.json()["id"]

        response2 = await async_client.post(
            "/api/v1/contacts/email",
            json={"email": email2},
            headers=auth_headers_for_user,
        )
        contact2_id = response2.json()["id"]

        # Send verification code to email1
        with patch("app.services.email_service.EmailService.send_verification_email", new_callable=AsyncMock):
            await async_client.post(
                f"/api/v1/contacts/{contact1_id}/send-verification",
                headers=auth_headers_for_user,
            )

        # Get the code for contact1
        result = await db_session.execute(
            select(VerificationCode)
            .where(VerificationCode.contact_id == uuid.UUID(contact1_id))
            .order_by(VerificationCode.created_at.desc())
        )
        verification_code = result.scalar_one()

        # Try to verify with contact2_id (wrong contact)
        verify_response = await async_client.post(
            "/api/v1/contacts/verify",
            json={"contact_id": contact2_id, "code": verification_code.code},
            headers=auth_headers_for_user,
        )

        assert verify_response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid verification code" in verify_response.json()["detail"]

    @pytest.mark.asyncio
    async def test_verify_code_cross_user(
        self,
        async_client: AsyncClient,
        auth_headers_for_user: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        another_user: User,
    ) -> None:
        """Test verifying code for contact belonging to another user fails."""
        email = make_unique_email()

        # Create contact for another_user directly in DB
        contact = EmailAddress(user_id=another_user.id, email=email, verified=False)
        db_session.add(contact)
        await db_session.commit()
        await db_session.refresh(contact)

        # Create verification code for that contact
        verification_code = VerificationCode(
            user_id=another_user.id,
            contact_id=contact.id,
            code="123456",
            type=VerificationType.EMAIL,
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
            used=False,
        )
        db_session.add(verification_code)
        await db_session.commit()

        # Try to verify using test_user's auth (should fail - different user)
        verify_response = await async_client.post(
            "/api/v1/contacts/verify",
            json={"contact_id": str(contact.id), "code": "123456"},
            headers=auth_headers_for_user,
        )

        assert verify_response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid verification code" in verify_response.json()["detail"]
