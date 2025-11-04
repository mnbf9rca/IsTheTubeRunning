"""Tests for notification service."""

import smtplib
from unittest.mock import AsyncMock, patch

import pytest
from app.schemas.tfl import DisruptionResponse
from app.services.notification_service import NotificationService


class TestNotificationService:
    """Test cases for notification service."""

    @pytest.mark.asyncio
    @patch("app.services.email_service.EmailService.send_email", new_callable=AsyncMock)
    async def test_send_disruption_email_success(self, mock_send_email: AsyncMock) -> None:
        """Test successful disruption email sending."""
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

        # Verify EmailService.send_email was called
        mock_send_email.assert_called_once()
        call_args = mock_send_email.call_args
        assert call_args[0][0] == email
        assert "Disruption Alert" in call_args[0][1]

    @pytest.mark.asyncio
    @patch("app.services.email_service.EmailService.send_email", new_callable=AsyncMock)
    async def test_send_disruption_email_correct_headers(self, mock_send_email: AsyncMock) -> None:
        """Test that disruption email has correct headers."""
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

        # Verify EmailService.send_email was called with correct parameters
        mock_send_email.assert_called_once()
        call_args = mock_send_email.call_args
        assert call_args[0][0] == email
        assert call_args[0][1] == f"⚠️ Disruption Alert: {route_name}"

    @pytest.mark.asyncio
    @patch("app.services.email_service.EmailService.send_email", new_callable=AsyncMock)
    async def test_send_disruption_email_with_multiple_disruptions(self, mock_send_email: AsyncMock) -> None:
        """Test email with multiple disruptions."""
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
        mock_send_email.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.email_service.EmailService.send_email", new_callable=AsyncMock)
    async def test_send_disruption_email_smtp_error_raises(self, mock_send_email: AsyncMock) -> None:
        """Test that SMTP errors are raised."""
        mock_send_email.side_effect = smtplib.SMTPException("Connection failed")

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
    @patch("app.services.sms_service.SmsService.send_sms", new_callable=AsyncMock)
    async def test_send_disruption_sms_success(self, mock_send_sms: AsyncMock) -> None:
        """Test successful SMS sending."""
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

        await service.send_disruption_sms(phone, route_name, disruptions)

        # Verify SmsService.send_sms was called
        mock_send_sms.assert_called_once()
        call_args = mock_send_sms.call_args
        assert call_args[0][0] == phone
        assert "TfL Alert" in call_args[0][1]

    @pytest.mark.asyncio
    @patch("app.services.sms_service.SmsService.send_sms", new_callable=AsyncMock)
    async def test_send_disruption_sms_multiple_disruptions(self, mock_send_sms: AsyncMock) -> None:
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

        await service.send_disruption_sms(phone, route_name, disruptions)

        # Verify SmsService.send_sms was called
        mock_send_sms.assert_called_once()

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
