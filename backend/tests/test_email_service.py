"""Tests for email service."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import aiosmtplib
import pytest
from app.services.email_service import EmailService, get_tls_settings


class TestGetTlsSettings:
    """Test cases for get_tls_settings pure function."""

    @pytest.mark.parametrize(
        ("port", "require_tls", "expected"),
        [
            # Port 465 uses implicit TLS regardless of require_tls
            (465, False, (True, None)),
            (465, True, (True, None)),
            # Port 587 with require_tls=False uses auto-upgrade
            (587, False, (False, None)),
            # Port 587 with require_tls=True forces STARTTLS
            (587, True, (False, True)),
            # Port 25 with require_tls=False uses auto-upgrade
            (25, False, (False, None)),
            # Port 25 with require_tls=True forces STARTTLS
            (25, True, (False, True)),
        ],
    )
    def test_get_tls_settings(self, port: int, require_tls: bool, expected: tuple[bool, bool | None]) -> None:
        """Test get_tls_settings with various port and TLS configurations."""
        assert get_tls_settings(port, require_tls) == expected


class TestEmailService:
    """Test cases for email service."""

    @pytest.mark.asyncio
    @patch("app.services.email_service.aiosmtplib.SMTP")
    async def test_send_verification_email_success(self, mock_smtp_class: MagicMock) -> None:
        """Test successful verification email sending."""
        mock_server = AsyncMock()
        mock_smtp_class.return_value.__aenter__.return_value = mock_server

        service = EmailService()
        await service.send_verification_email("test@example.com", "123456")

        mock_server.login.assert_called_once()
        mock_server.send_message.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.email_service.aiosmtplib.SMTP")
    async def test_send_verification_email_correct_headers(self, mock_smtp_class: MagicMock) -> None:
        """Test that email has correct headers."""
        mock_server = AsyncMock()
        mock_smtp_class.return_value.__aenter__.return_value = mock_server

        service = EmailService()
        await service.send_verification_email("test@example.com", "123456")

        call_args = mock_server.send_message.call_args
        message = call_args[0][0]

        assert message["To"] == "test@example.com"
        assert message["Subject"] == "Verify Your Email - IsTheTubeRunning"
        assert message["From"] == service.from_email

    @pytest.mark.asyncio
    @patch("app.services.email_service.aiosmtplib.SMTP")
    async def test_send_verification_email_smtp_error_raises(self, mock_smtp_class: MagicMock) -> None:
        """Test that SMTP errors are raised."""
        mock_server = AsyncMock()
        mock_server.send_message.side_effect = aiosmtplib.SMTPException("Connection failed")
        mock_smtp_class.return_value.__aenter__.return_value = mock_server

        service = EmailService()

        with pytest.raises(aiosmtplib.SMTPException):
            await service.send_verification_email("test@example.com", "123456")

    @pytest.mark.asyncio
    @patch("app.services.email_service.aiosmtplib.SMTP")
    async def test_send_verification_email_timeout(self, mock_smtp_class: MagicMock) -> None:
        """Test SMTP timeout exception handling."""
        mock_server = AsyncMock()
        mock_server.send_message.side_effect = TimeoutError("Timeout occurred")
        mock_smtp_class.return_value.__aenter__.return_value = mock_server

        service = EmailService()

        with pytest.raises(asyncio.TimeoutError):
            await service.send_verification_email("test@example.com", "123456")

    @pytest.mark.asyncio
    @patch("app.services.email_service.aiosmtplib.SMTP")
    async def test_send_verification_email_connection_refused(self, mock_smtp_class: MagicMock) -> None:
        """Test network error handling when SMTP connection is refused."""
        mock_server = AsyncMock()
        mock_server.send_message.side_effect = ConnectionRefusedError("Connection refused")
        mock_smtp_class.return_value.__aenter__.return_value = mock_server

        service = EmailService()

        with pytest.raises(ConnectionRefusedError):
            await service.send_verification_email("test@example.com", "123456")
