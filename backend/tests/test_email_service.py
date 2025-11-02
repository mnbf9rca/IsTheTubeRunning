"""Tests for email service."""

import smtplib
from unittest.mock import MagicMock, patch

import pytest
from app.services.email_service import EmailService


class TestEmailService:
    """Test cases for email service."""

    @pytest.mark.asyncio
    @patch("app.services.email_service.smtplib.SMTP")
    async def test_send_verification_email_success(self, mock_smtp_class: MagicMock) -> None:
        """Test successful verification email sending."""
        # Setup mock SMTP server
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        service = EmailService()
        email = "test@example.com"
        code = "123456"

        await service.send_verification_email(email, code)

        # Verify SMTP methods were called
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once()
        mock_server.send_message.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.email_service.smtplib.SMTP")
    async def test_send_verification_email_correct_headers(self, mock_smtp_class: MagicMock) -> None:
        """Test that email has correct headers."""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        service = EmailService()
        email = "test@example.com"
        code = "123456"

        await service.send_verification_email(email, code)

        # Get the message that was sent
        call_args = mock_server.send_message.call_args
        message = call_args[0][0]

        assert message["To"] == email
        assert message["Subject"] == "Verify Your Email - IsTheTubeRunning"
        assert message["From"] == service.from_email

    @pytest.mark.asyncio
    @patch("app.services.email_service.smtplib.SMTP")
    async def test_send_verification_email_smtp_error_raises(self, mock_smtp_class: MagicMock) -> None:
        """Test that SMTP errors are raised."""
        mock_server = MagicMock()
        mock_server.send_message.side_effect = smtplib.SMTPException("Connection failed")
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        service = EmailService()
        email = "test@example.com"
        code = "123456"

        with pytest.raises(smtplib.SMTPException):
            await service.send_verification_email(email, code)

    @pytest.mark.asyncio
    @patch("app.services.email_service.smtplib.SMTP")
    async def test_send_verification_email_uses_correct_smtp_config(self, mock_smtp_class: MagicMock) -> None:
        """Test that email service uses correct SMTP configuration."""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        service = EmailService()

        # Verify SMTP config is loaded
        assert service.smtp_host is not None
        assert service.smtp_port is not None
        assert service.smtp_user is not None
        assert service.smtp_password is not None
        assert service.from_email is not None

        await service.send_verification_email("test@example.com", "123456")

        # Verify SMTP was initialized with correct host/port
        mock_smtp_class.assert_called_once_with(service.smtp_host, service.smtp_port)
