"""Tests for verification service."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.models.rate_limit import RateLimitAction, RateLimitLog
from app.models.user import EmailAddress, PhoneNumber, User, VerificationCode, VerificationType
from app.services.verification_service import VerificationService
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class TestVerificationService:
    """Test cases for verification service."""

    @pytest.mark.asyncio
    async def test_generate_code_returns_six_digits(self, db_session: AsyncSession) -> None:
        """Test that code generation returns a 6-digit string."""
        service = VerificationService(db_session)
        code = service.generate_code()

        assert len(code) == 6
        assert code.isdigit()

    @pytest.mark.asyncio
    async def test_generate_code_is_random(self, db_session: AsyncSession) -> None:
        """Test that code generation produces different codes."""
        service = VerificationService(db_session)
        codes = {service.generate_code() for _ in range(100)}

        # Should have generated multiple unique codes
        assert len(codes) > 1

    @pytest.mark.asyncio
    async def test_check_verification_rate_limit_allows_first_requests(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Test that rate limit allows the first few requests."""
        service = VerificationService(db_session)
        contact_id = uuid4()

        # Should not raise for first 3 requests
        for _ in range(3):
            await service.check_verification_rate_limit(contact_id)
            # Record the request
            await service.record_verification_code_request(contact_id, test_user.id)

    @pytest.mark.asyncio
    async def test_check_verification_rate_limit_blocks_after_limit(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Test that rate limit blocks requests after limit is exceeded."""
        service = VerificationService(db_session)
        contact_id = uuid4()

        # Record 3 requests
        for _ in range(3):
            await service.record_verification_code_request(contact_id, test_user.id)

        # 4th request should be blocked
        with pytest.raises(HTTPException) as exc_info:
            await service.check_verification_rate_limit(contact_id)

        assert exc_info.value.status_code == 429
        assert "Too many verification code requests" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_check_verification_rate_limit_ignores_old_requests(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Test that rate limit ignores requests older than the window."""
        service = VerificationService(db_session)
        contact_id = uuid4()

        # Record 3 old requests (2 hours ago)
        old_timestamp = datetime.now(UTC) - timedelta(hours=2)
        for _ in range(3):
            log_entry = RateLimitLog(
                user_id=test_user.id,
                action_type=RateLimitAction.VERIFY_CODE,
                resource_id=str(contact_id),
                timestamp=old_timestamp,
            )
            db_session.add(log_entry)
        await db_session.commit()

        # Should allow new request since old ones are outside the window
        await service.check_verification_rate_limit(contact_id)

    @pytest.mark.asyncio
    async def test_check_add_contact_rate_limit_allows_first_requests(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Test that add contact rate limit allows first few requests."""
        service = VerificationService(db_session)

        # Should not raise for first 5 requests
        for i in range(5):
            await service.check_add_contact_rate_limit(test_user.id)
            await service.record_add_contact_failure(test_user.id, f"test{i}@example.com")

    @pytest.mark.asyncio
    async def test_check_add_contact_rate_limit_blocks_after_limit(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Test that add contact rate limit blocks after limit exceeded."""
        service = VerificationService(db_session)

        # Record 5 failures
        for i in range(5):
            await service.record_add_contact_failure(test_user.id, f"test{i}@example.com")

        # 6th request should be blocked
        with pytest.raises(HTTPException) as exc_info:
            await service.check_add_contact_rate_limit(test_user.id)

        assert exc_info.value.status_code == 429
        assert "Too many failed attempts" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_reset_verification_rate_limit_clears_logs(self, db_session: AsyncSession, test_user: User) -> None:
        """Test that resetting rate limit clears the logs."""
        service = VerificationService(db_session)
        contact_id = uuid4()

        # Record 3 requests
        for _ in range(3):
            await service.record_verification_code_request(contact_id, test_user.id)

        # Reset rate limit
        await service.reset_verification_rate_limit(contact_id)

        # Should allow new requests now
        await service.check_verification_rate_limit(contact_id)

    @pytest.mark.asyncio
    @patch("app.services.verification_service.EmailService.send_verification_email")
    async def test_create_and_send_code_email(
        self, mock_send_email: AsyncMock, db_session: AsyncSession, test_user: User
    ) -> None:
        """Test creating and sending verification code via email."""
        mock_send_email.return_value = None

        service = VerificationService(db_session)
        contact_id = uuid4()
        email = "test@example.com"

        await service.create_and_send_code(
            contact_id=contact_id,
            user_id=test_user.id,
            contact_type=VerificationType.EMAIL,
            contact_value=email,
        )

        # Verify email was sent
        mock_send_email.assert_called_once()
        call_args = mock_send_email.call_args
        assert call_args[0][0] == email
        assert len(call_args[0][1]) == 6

        # Verify code was created in database
        result = await db_session.execute(select(VerificationCode).where(VerificationCode.user_id == test_user.id))
        code = result.scalar_one()
        assert code.type == VerificationType.EMAIL
        assert not code.used

    @pytest.mark.asyncio
    @patch("app.services.verification_service.SmsService.send_verification_sms")
    async def test_create_and_send_code_sms(
        self, mock_send_sms: AsyncMock, db_session: AsyncSession, test_user: User
    ) -> None:
        """Test creating and sending verification code via SMS."""
        mock_send_sms.return_value = None

        service = VerificationService(db_session)
        contact_id = uuid4()
        phone = "+14155552671"

        await service.create_and_send_code(
            contact_id=contact_id,
            user_id=test_user.id,
            contact_type=VerificationType.SMS,
            contact_value=phone,
        )

        # Verify SMS was sent
        mock_send_sms.assert_called_once()
        call_args = mock_send_sms.call_args
        assert call_args[0][0] == phone
        assert len(call_args[0][1]) == 6

        # Verify code was created in database
        result = await db_session.execute(select(VerificationCode).where(VerificationCode.user_id == test_user.id))
        code = result.scalar_one()
        assert code.type == VerificationType.SMS
        assert not code.used

    @pytest.mark.asyncio
    @patch("app.services.verification_service.EmailService.send_verification_email")
    async def test_create_and_send_code_respects_rate_limit(
        self, mock_send_email: AsyncMock, db_session: AsyncSession, test_user: User
    ) -> None:
        """Test that code sending respects rate limit."""
        mock_send_email.return_value = None

        service = VerificationService(db_session)
        contact_id = uuid4()
        email = "test@example.com"

        # Send 3 codes (should work)
        for _ in range(3):
            await service.create_and_send_code(
                contact_id=contact_id,
                user_id=test_user.id,
                contact_type=VerificationType.EMAIL,
                contact_value=email,
            )

        # 4th attempt should fail
        with pytest.raises(HTTPException) as exc_info:
            await service.create_and_send_code(
                contact_id=contact_id,
                user_id=test_user.id,
                contact_type=VerificationType.EMAIL,
                contact_value=email,
            )

        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_verify_code_success_email(self, db_session: AsyncSession, test_user: User) -> None:
        """Test successful code verification for email."""
        service = VerificationService(db_session)

        # Create email address
        email = EmailAddress(
            user_id=test_user.id,
            email="test@example.com",
            verified=False,
            is_primary=True,
        )
        db_session.add(email)
        await db_session.commit()
        await db_session.refresh(email)

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

        # Verify the code
        result = await service.verify_code(code, email.id, test_user.id)

        assert result is True

        # Check email is now verified
        await db_session.refresh(email)
        assert email.verified is True

        # Check code is marked as used
        await db_session.refresh(verification_code)
        assert verification_code.used is True

    @pytest.mark.asyncio
    async def test_verify_code_success_phone(self, db_session: AsyncSession, test_user: User) -> None:
        """Test successful code verification for phone."""
        service = VerificationService(db_session)

        # Create phone number
        phone = PhoneNumber(
            user_id=test_user.id,
            phone="+14155552671",
            verified=False,
            is_primary=True,
        )
        db_session.add(phone)
        await db_session.commit()
        await db_session.refresh(phone)

        # Create verification code
        code = "654321"
        verification_code = VerificationCode(
            user_id=test_user.id,
            code=code,
            type=VerificationType.SMS,
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
            used=False,
        )
        db_session.add(verification_code)
        await db_session.commit()

        # Verify the code
        result = await service.verify_code(code, phone.id, test_user.id)

        assert result is True

        # Check phone is now verified
        await db_session.refresh(phone)
        assert phone.verified is True

        # Check code is marked as used
        await db_session.refresh(verification_code)
        assert verification_code.used is True

    @pytest.mark.asyncio
    async def test_verify_code_invalid_code(self, db_session: AsyncSession, test_user: User) -> None:
        """Test verification with invalid code."""
        service = VerificationService(db_session)
        contact_id = uuid4()

        with pytest.raises(HTTPException) as exc_info:
            await service.verify_code("999999", contact_id, test_user.id)

        assert exc_info.value.status_code == 400
        assert "Invalid verification code" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_verify_code_expired_code(self, db_session: AsyncSession, test_user: User) -> None:
        """Test verification with expired code."""
        service = VerificationService(db_session)

        # Create email address
        email = EmailAddress(
            user_id=test_user.id,
            email="test@example.com",
            verified=False,
            is_primary=True,
        )
        db_session.add(email)
        await db_session.commit()
        await db_session.refresh(email)

        # Create expired verification code
        code = "123456"
        verification_code = VerificationCode(
            user_id=test_user.id,
            code=code,
            type=VerificationType.EMAIL,
            expires_at=datetime.now(UTC) - timedelta(minutes=1),  # Expired
            used=False,
        )
        db_session.add(verification_code)
        await db_session.commit()

        # Try to verify expired code
        with pytest.raises(HTTPException) as exc_info:
            await service.verify_code(code, email.id, test_user.id)

        assert exc_info.value.status_code == 400
        assert "expired" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_verify_code_already_used(self, db_session: AsyncSession, test_user: User) -> None:
        """Test verification with already used code."""
        service = VerificationService(db_session)

        # Create email address
        email = EmailAddress(
            user_id=test_user.id,
            email="test@example.com",
            verified=False,
            is_primary=True,
        )
        db_session.add(email)
        await db_session.commit()
        await db_session.refresh(email)

        # Create verification code
        code = "123456"
        verification_code = VerificationCode(
            user_id=test_user.id,
            code=code,
            type=VerificationType.EMAIL,
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
            used=True,  # Already used
        )
        db_session.add(verification_code)
        await db_session.commit()

        # Try to verify used code
        with pytest.raises(HTTPException) as exc_info:
            await service.verify_code(code, email.id, test_user.id)

        assert exc_info.value.status_code == 400
        assert "Invalid verification code" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_verify_code_resets_rate_limit(self, db_session: AsyncSession, test_user: User) -> None:
        """Test that successful verification resets rate limit."""
        service = VerificationService(db_session)

        # Create email address
        email = EmailAddress(
            user_id=test_user.id,
            email="test@example.com",
            verified=False,
            is_primary=True,
        )
        db_session.add(email)
        await db_session.commit()
        await db_session.refresh(email)

        # Create rate limit entries
        for _ in range(3):
            await service.record_verification_code_request(email.id, test_user.id)

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

        # Verify the code
        await service.verify_code(code, email.id, test_user.id)

        # Check that rate limit was reset
        result = await db_session.execute(
            select(RateLimitLog).where(
                RateLimitLog.resource_id == str(email.id),
                RateLimitLog.action_type == RateLimitAction.VERIFY_CODE,
            )
        )
        logs = result.scalars().all()
        assert len(logs) == 0
