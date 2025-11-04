"""Tests for notification service."""

import smtplib
from unittest.mock import MagicMock, patch

import pytest
from app.schemas.tfl import DisruptionResponse
from app.services.notification_service import NotificationService


class TestNotificationService:
    """Test cases for notification service."""

    @pytest.mark.asyncio
    @patch("app.services.notification_service.smtplib.SMTP")
    async def test_send_disruption_email_success(self, mock_smtp_class: MagicMock) -> None:
        """Test successful disruption email sending."""
        # Setup mock SMTP server
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        service = NotificationService()
        email = "test@example.com"
        route_name = "Morning Commute"
        disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                status_severity=6,
                status_severity_description="Minor Delays",
                reason="Signal failure at Oxford Circus",
            )
        ]

        await service.send_disruption_email(email, route_name, disruptions)

        # Verify SMTP methods were called
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once()
        mock_server.send_message.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.notification_service.smtplib.SMTP")
    async def test_send_disruption_email_correct_headers(self, mock_smtp_class: MagicMock) -> None:
        """Test that disruption email has correct headers."""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        service = NotificationService()
        email = "test@example.com"
        route_name = "Morning Commute"
        disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                status_severity=6,
                status_severity_description="Minor Delays",
                reason=None,
            )
        ]

        await service.send_disruption_email(email, route_name, disruptions, user_name="John")

        # Get the message that was sent
        call_args = mock_server.send_message.call_args
        message = call_args[0][0]

        assert message["To"] == email
        assert message["Subject"] == f"⚠️ Disruption Alert: {route_name}"
        assert message["From"] == service.email_service.from_email

    @pytest.mark.asyncio
    @patch("app.services.notification_service.smtplib.SMTP")
    async def test_send_disruption_email_with_multiple_disruptions(self, mock_smtp_class: MagicMock) -> None:
        """Test email with multiple disruptions."""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        service = NotificationService()
        email = "test@example.com"
        route_name = "Morning Commute"
        disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                status_severity=6,
                status_severity_description="Minor Delays",
                reason="Signal failure",
            ),
            DisruptionResponse(
                line_id="northern",
                line_name="Northern",
                status_severity=3,
                status_severity_description="Severe Delays",
                reason="Train breakdown",
            ),
        ]

        await service.send_disruption_email(email, route_name, disruptions)

        # Verify email was sent
        mock_server.send_message.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.notification_service.smtplib.SMTP")
    async def test_send_disruption_email_smtp_error_raises(self, mock_smtp_class: MagicMock) -> None:
        """Test that SMTP errors are raised."""
        mock_server = MagicMock()
        mock_server.send_message.side_effect = smtplib.SMTPException("Connection failed")
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        service = NotificationService()
        email = "test@example.com"
        route_name = "Morning Commute"
        disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                status_severity=6,
                status_severity_description="Minor Delays",
            )
        ]

        with pytest.raises(smtplib.SMTPException):
            await service.send_disruption_email(email, route_name, disruptions)

    @pytest.mark.asyncio
    @patch("app.services.notification_service.SMS_LOG_FILE", None)
    async def test_send_disruption_sms_success(self) -> None:
        """Test successful SMS sending (stub mode - no file logging)."""
        service = NotificationService()
        phone = "+442071234567"
        route_name = "Morning Commute"
        disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                status_severity=6,
                status_severity_description="Minor Delays",
                reason="Signal failure",
            )
        ]

        # Should not raise
        await service.send_disruption_sms(phone, route_name, disruptions)

    @pytest.mark.asyncio
    @patch("app.services.notification_service.SMS_LOG_FILE", None)
    async def test_send_disruption_sms_multiple_disruptions(self) -> None:
        """Test SMS with multiple disruptions (should be concise)."""
        service = NotificationService()
        phone = "+442071234567"
        route_name = "Morning Commute"
        disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                status_severity=6,
                status_severity_description="Minor Delays",
            ),
            DisruptionResponse(
                line_id="northern",
                line_name="Northern",
                status_severity=3,
                status_severity_description="Severe Delays",
            ),
            DisruptionResponse(
                line_id="central",
                line_name="Central",
                status_severity=6,
                status_severity_description="Minor Delays",
            ),
        ]

        # Should not raise and should handle multiple disruptions
        await service.send_disruption_sms(phone, route_name, disruptions)

    @pytest.mark.asyncio
    async def test_render_email_template_success(self) -> None:
        """Test email template rendering."""
        service = NotificationService()
        disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                status_severity=6,
                status_severity_description="Minor Delays",
                reason="Signal failure",
            )
        ]

        html = service._render_email_template(
            "email/disruption_alert.html",
            {
                "route_name": "Test Route",
                "user_name": "John",
                "disruptions": disruptions,
                "tfl_status_url": "https://tfl.gov.uk/tube-dlr-overground/status/",
            },
        )

        # Verify template contains key elements
        assert "Test Route" in html
        assert "Victoria" in html
        assert "Minor Delays" in html

    @pytest.mark.asyncio
    async def test_render_email_template_with_reason(self) -> None:
        """Test template rendering with disruption reason."""
        service = NotificationService()
        disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                status_severity=6,
                status_severity_description="Minor Delays",
                reason="Signal failure at Oxford Circus",
            )
        ]

        html = service._render_email_template(
            "email/disruption_alert.html",
            {
                "route_name": "Test Route",
                "user_name": None,
                "disruptions": disruptions,
                "tfl_status_url": "https://tfl.gov.uk/tube-dlr-overground/status/",
            },
        )

        # Verify reason is included
        assert "Signal failure at Oxford Circus" in html

    @pytest.mark.asyncio
    async def test_render_email_template_without_user_name(self) -> None:
        """Test template rendering defaults to 'there' when no user name."""
        service = NotificationService()
        disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                status_severity=6,
                status_severity_description="Minor Delays",
            )
        ]

        html = service._render_email_template(
            "email/disruption_alert.html",
            {
                "route_name": "Test Route",
                "user_name": None,
                "disruptions": disruptions,
                "tfl_status_url": "https://tfl.gov.uk/tube-dlr-overground/status/",
            },
        )

        # Verify "there" appears as default greeting
        assert "Hello there" in html or "there" in html.lower()
