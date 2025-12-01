"""Tests for SMS service."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from app.core.config import settings
from app.services import sms_service
from app.services.sms_service import SMS_LOG_FILE, SmsService
from app.utils.pii import hash_pii


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
        """Test that SMS is logged with correct format and PII is hashed."""
        service = SmsService()
        phone = "+14155552671"
        code = "123456"

        await service.send_verification_sms(phone, code)

        assert SMS_LOG_FILE is not None
        content = SMS_LOG_FILE.read_text()

        # Verify phone is hashed, not logged in plain text
        phone_hash = hash_pii(phone)
        assert phone_hash in content
        assert phone not in content

        # Verify message content is present
        assert code in content
        assert "IsTheTubeRunning verification code" in content
        assert "expires in 15 minutes" in content

    @pytest.mark.asyncio
    async def test_send_verification_sms_appends_to_existing_file(self) -> None:
        """Test that multiple SMS sends append to the same file with hashed phones."""
        service = SmsService()
        phone1 = "+14155552671"
        phone2 = "+14155552672"

        await service.send_verification_sms(phone1, "111111")
        await service.send_verification_sms(phone2, "222222")

        assert SMS_LOG_FILE is not None
        content = SMS_LOG_FILE.read_text()

        # Verify phones are hashed, not logged in plain text
        assert hash_pii(phone1) in content
        assert hash_pii(phone2) in content
        assert phone1 not in content
        assert phone2 not in content

        # Verify message content is present
        assert "111111" in content
        assert "222222" in content

    @pytest.mark.asyncio
    async def test_send_verification_sms_handles_special_characters(self) -> None:
        """Test that SMS service handles phone numbers with special characters and hashes them."""
        service = SmsService()
        phone = "+1 (415) 555-2671"
        code = "999999"

        await service.send_verification_sms(phone, code)

        assert SMS_LOG_FILE is not None
        content = SMS_LOG_FILE.read_text()

        # Verify phone is hashed, not logged in plain text (even with special chars)
        assert hash_pii(phone) in content
        assert phone not in content
        assert code in content

    @pytest.mark.asyncio
    async def test_send_verification_sms_when_log_file_is_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that SMS service handles case when SMS_LOG_FILE is None."""
        # Temporarily set SMS_LOG_FILE to None
        monkeypatch.setattr(sms_service, "SMS_LOG_FILE", None)

        service = SmsService()
        phone = "+14155552671"
        code = "123456"

        # Should not raise exception even when file logging is disabled
        await service.send_verification_sms(phone, code)

    def test_write_to_file_sync_when_sms_log_file_is_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that _write_to_file_sync handles None SMS_LOG_FILE."""
        # Set SMS_LOG_FILE to None
        monkeypatch.setattr(sms_service, "SMS_LOG_FILE", None)

        service = SmsService()

        # Should not raise exception (early return)
        service._write_to_file_sync("+14155552671", "test message", "2025-01-01T00:00:00Z")

    def test_write_to_file_sync_handles_os_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that _write_to_file_sync handles OSError gracefully."""
        # Create a readonly directory to trigger OSError
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        log_file = readonly_dir / "sms_log.txt"

        # Make directory readonly (removes write permission)
        readonly_dir.chmod(0o444)

        try:
            monkeypatch.setattr(sms_service, "SMS_LOG_FILE", log_file)

            service = SmsService()

            # Should log error but not raise exception
            service._write_to_file_sync("+14155552671", "test message", "2025-01-01T00:00:00Z")
        finally:
            # Restore write permission for cleanup
            readonly_dir.chmod(0o755)

    def test_get_sms_log_file_when_dir_not_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test _get_sms_log_file returns None when SMS_LOG_DIR is not configured."""
        # Set SMS_LOG_DIR to empty string
        monkeypatch.setattr(settings, "SMS_LOG_DIR", "")

        result = sms_service._get_sms_log_file()

        assert result is None

    def test_get_sms_log_file_when_dir_not_writable(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test _get_sms_log_file returns None when SMS_LOG_DIR is not writable."""
        # Create a directory path that will fail on mkdir
        bad_dir = tmp_path / "readonly"
        monkeypatch.setattr(settings, "SMS_LOG_DIR", str(bad_dir))

        # Mock Path to raise PermissionError on mkdir
        mock_path_instance = MagicMock()
        mock_path_instance.mkdir.side_effect = PermissionError("Permission denied")

        # Mock the Path class to return our mock instance
        def mock_path(path_str: str) -> Path | MagicMock:
            return mock_path_instance if path_str == str(bad_dir) else Path(path_str)

        monkeypatch.setattr(sms_service, "Path", mock_path)

        result = sms_service._get_sms_log_file()

        assert result is None
