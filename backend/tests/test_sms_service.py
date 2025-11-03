"""Tests for SMS service."""

from collections.abc import Generator

import pytest
from app.services.sms_service import SMS_LOG_FILE, SmsService


class TestSmsService:
    """Test cases for SMS service."""

    @pytest.fixture(autouse=True)
    def cleanup_sms_log(self) -> Generator[None]:
        """Clean up SMS log file before and after each test."""
        if SMS_LOG_FILE and SMS_LOG_FILE.exists():
            SMS_LOG_FILE.unlink()
        yield
        if SMS_LOG_FILE and SMS_LOG_FILE.exists():
            SMS_LOG_FILE.unlink()

    @pytest.mark.asyncio
    async def test_send_verification_sms_creates_log_file(self) -> None:
        """Test that sending SMS creates a log file."""
        service = SmsService()
        phone = "+14155552671"
        code = "123456"

        await service.send_verification_sms(phone, code)

        assert SMS_LOG_FILE is not None
        assert SMS_LOG_FILE.exists()

    @pytest.mark.asyncio
    async def test_send_verification_sms_logs_correct_format(self) -> None:
        """Test that SMS is logged with correct format."""
        service = SmsService()
        phone = "+14155552671"
        code = "123456"

        await service.send_verification_sms(phone, code)

        assert SMS_LOG_FILE is not None
        content = SMS_LOG_FILE.read_text()

        assert phone in content
        assert code in content
        assert "IsTheTubeRunning verification code" in content
        assert "expires in 15 minutes" in content

    @pytest.mark.asyncio
    async def test_send_verification_sms_appends_to_existing_file(self) -> None:
        """Test that multiple SMS sends append to the same file."""
        service = SmsService()

        await service.send_verification_sms("+14155552671", "111111")
        await service.send_verification_sms("+14155552672", "222222")

        assert SMS_LOG_FILE is not None
        content = SMS_LOG_FILE.read_text()

        assert "+14155552671" in content
        assert "111111" in content
        assert "+14155552672" in content
        assert "222222" in content

    @pytest.mark.asyncio
    async def test_send_verification_sms_handles_special_characters(self) -> None:
        """Test that SMS service handles phone numbers with special characters."""
        service = SmsService()
        phone = "+1 (415) 555-2671"
        code = "999999"

        await service.send_verification_sms(phone, code)

        assert SMS_LOG_FILE is not None
        content = SMS_LOG_FILE.read_text()

        assert phone in content
        assert code in content
