"""Tests for email service."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import aiosmtplib
import pytest
from app.services.email_service import EmailService, get_tls_settings


class TestGetTlsSettings:
    """Test cases for get_tls_settings pure function."""

    def test_port_465_implicit_tls(self) -> None:
        """Port 465 uses implicit TLS regardless of require_tls."""
        assert get_tls_settings(465, False) == (True, None)
        assert get_tls_settings(465, True) == (True, None)

    def test_port_587_auto_upgrade(self) -> None:
        """Port 587 with require_tls=False uses auto-upgrade."""
        assert get_tls_settings(587, False) == (False, None)

    def test_port_587_require_tls(self) -> None:
        """Port 587 with require_tls=True forces STARTTLS."""
        assert get_tls_settings(587, True) == (False, True)

    def test_port_25_auto_upgrade(self) -> None:
        """Port 25 with require_tls=False uses auto-upgrade."""
        assert get_tls_settings(25, False) == (False, None)

    def test_port_25_require_tls(self) -> None:
        """Port 25 with require_tls=True forces STARTTLS."""
        assert get_tls_settings(25, True) == (False, True)


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
