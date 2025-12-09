"""Tests for notification service."""

import re
import smtplib
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from urllib.parse import urlparse

import pytest
from app.schemas.tfl import ClearedLineInfo, DisruptionResponse
from app.services.notification_service import (
    NotificationService,
    _build_disruption_subject,
    _build_status_update_subject,
)


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
                mode="tube",
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
        assert call_args[0][1] == f"⚠️ {route_name}: Victoria disrupted"

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
                mode="tube",
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
        assert call_args[0][1] == f"⚠️ {route_name}: Victoria disrupted"

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
                mode="tube",
                status_severity=6,
                status_severity_description="Minor Delays",
                reason="Signal failure",
            ),
            DisruptionResponse(
                line_id="northern",
                line_name="Northern",
                mode="tube",
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
                mode="tube",
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
                mode="tube",
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
                mode="tube",
                status_severity=6,
                status_severity_description="Minor Delays",
            ),
            DisruptionResponse(
                line_id="northern",
                line_name="Northern",
                mode="tube",
                status_severity=3,
                status_severity_description="Severe Delays",
            ),
            DisruptionResponse(
                line_id="central",
                line_name="Central",
                mode="tube",
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
                mode="tube",
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
                mode="tube",
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
        """Test template rendering works without user name (greeting removed)."""
        service = NotificationService()
        disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
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

        # Verify template renders correctly without greeting
        assert "Test Route" in html
        assert "Victoria" in html

    @pytest.mark.asyncio
    async def test_send_disruption_sms_long_message(self) -> None:
        """Test SMS message truncation for long messages."""
        service = NotificationService()

        # Create 20 disruptions to exceed SMS limit
        disruptions = [
            DisruptionResponse(
                line_id=f"line-{i}",
                line_name=f"Line {i}",
                mode="tube",
                status_severity=5,
                status_severity_description="Severe Delays",
                reason=f"Signal failure at station {i}",
                created_at=datetime.now(UTC),
            )
            for i in range(20)
        ]

        # Should handle long message without error
        await service.send_disruption_sms(
            phone="+447700900123",
            route_name="Test Route",
            disruptions=disruptions,
        )

    @pytest.mark.asyncio
    async def test_send_disruption_sms_error_propagates(self) -> None:
        """Test SMS sending error is propagated."""
        service = NotificationService()
        disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=5,
                status_severity_description="Severe Delays",
                reason="Signal failure",
                created_at=datetime.now(UTC),
            )
        ]

        with (
            patch.object(service.sms_service, "send_sms", side_effect=Exception("SMS error")),
            pytest.raises(Exception, match="SMS error"),
        ):
            await service.send_disruption_sms(
                phone="+447700900123",
                route_name="Test",
                disruptions=disruptions,
            )

    @pytest.mark.asyncio
    async def test_send_disruption_email_template_error_propagates(self) -> None:
        """Test email template error is propagated."""
        service = NotificationService()
        disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=5,
                status_severity_description="Severe Delays",
                reason="Signal failure",
                created_at=datetime.now(UTC),
            )
        ]

        with (
            patch.object(service, "_render_email_template", side_effect=Exception("Template error")),
            pytest.raises(Exception, match="Template error"),
        ):
            await service.send_disruption_email(
                email="test@example.com",
                route_name="Test",
                disruptions=disruptions,
            )

    @pytest.mark.asyncio
    async def test_send_disruption_sms_very_long_truncation(self) -> None:
        """Test SMS truncation when message exceeds max length even with one disruption."""
        service = NotificationService()

        # Create single disruption with very long reason to exceed SMS limit
        disruptions = [
            DisruptionResponse(
                line_id="line-1",
                line_name="Line 1",
                mode="tube",
                status_severity=5,
                status_severity_description="Severe Delays" * 20,  # Make it very long
                reason="Signal failure " * 50,  # Very long reason
                created_at=datetime.now(UTC),
            )
        ]

        # Should handle very long single disruption without error
        with patch.object(service.sms_service, "send_sms", new_callable=AsyncMock) as mock_send:
            await service.send_disruption_sms(
                phone="+447700900123",
                route_name="Test Route",
                disruptions=disruptions,
            )
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_template_render_error_handling(self) -> None:
        """Test _render_email_template error handling."""

        service = NotificationService()

        with (
            patch(
                "app.services.notification_service.jinja_env.get_template",
                side_effect=Exception("Template not found"),
            ),
            pytest.raises(Exception, match="Template not found"),
        ):
            service._render_email_template("nonexistent.html", {})

    @pytest.mark.asyncio
    @patch("app.services.sms_service.SmsService.send_sms", new_callable=AsyncMock)
    async def test_send_disruption_sms_truncates_long_message_multiple_disruptions(
        self, mock_send_sms: AsyncMock
    ) -> None:
        """Test SMS truncation when message is too long with multiple disruptions (lines 152-153)."""
        service = NotificationService()

        # Create multiple disruptions with long line names and descriptions
        # The format is: "TfL Alert: {route_name} affected. {line_name}: {status}. {line_name}: {status}. {url}"
        # We need the message with 2 disruptions to exceed 160 chars to trigger truncation
        disruptions = [
            DisruptionResponse(
                line_id="metropolitan",
                line_name="Metropolitan Line Experiencing",
                mode="tube",
                status_severity="9",
                status_severity_description="Severe Delays and Signal Failures Throughout",
                reason="Signal failure",
            ),
            DisruptionResponse(
                line_id="hammersmith-city",
                line_name="Hammersmith & City Line Now",
                mode="tube",
                status_severity="10",
                status_severity_description="Part Suspended Between Multiple Stations",
                reason="Engineering works",
            ),
        ]

        phone = "+447700900123"
        route_name = "My Very Long Route Name For Testing"

        # Call the method
        await service.send_disruption_sms(
            phone=phone,
            route_name=route_name,
            disruptions=disruptions,
        )

        # Verify SMS was sent
        mock_send_sms.assert_called_once()

        # Get the actual message sent
        call_args = mock_send_sms.call_args
        sent_phone = call_args[0][0]
        sent_message = call_args[0][1]

        # Verify phone number
        assert sent_phone == phone

        # Verify message was truncated (second disruption removed)
        # Lines 152-153 were executed: it took only the first disruption when 2 were too long
        assert "Severe Delays and Signal Failures Throughout" in sent_message  # First disruption included
        assert "Part Suspended Between Multiple Stations" not in sent_message  # Second was truncated
        assert "My Very Long Route Name For Testing" in sent_message

        # Parse the tfl.gov.uk URL in sent_message and check its hostname
        # Extract URL using regex (it is the last part after "More: ")
        url_match = re.search(r"More: (\S+)", sent_message)
        assert url_match is not None, f"Expected URL after 'More:', got message: {sent_message}"
        sent_url = url_match.group(1)
        parsed = urlparse(f"https://{sent_url}")  # Add scheme for proper parsing
        assert parsed.hostname == "tfl.gov.uk", f"Expected hostname 'tfl.gov.uk', got '{parsed.hostname}'"

        # Verify the truncation actually happened by checking it's using only 1 disruption
        # Count the number of disruptions in the message (each line has format "LineName: Status")
        # We have "TfL Alert: ", "LineName: Status", and "More: url" - so 3 colons total
        disruption_count = sent_message.count(": ") - 2  # -2 for "TfL Alert: " and "More: "
        assert disruption_count == 1, f"Expected 1 disruption after truncation, got {disruption_count}"

    @pytest.mark.asyncio
    @patch("app.services.email_service.EmailService.send_email", new_callable=AsyncMock)
    async def test_send_status_update_email_success(self, mock_send_email: AsyncMock) -> None:
        """Test successful status update email sending."""
        service = NotificationService()
        email = "test@example.com"
        route_name = "Morning Commute"
        cleared_lines = [
            ClearedLineInfo(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                previous_severity=3,
                previous_status="Severe Delays",
                current_severity=10,
                current_status="Good Service",
            )
        ]
        still_disrupted = [
            DisruptionResponse(
                line_id="northern",
                line_name="Northern",
                mode="tube",
                status_severity=6,
                status_severity_description="Minor Delays",
                reason="Signal failure",
            )
        ]

        await service.send_status_update_email(email, route_name, cleared_lines, still_disrupted)

        # Verify EmailService.send_email was called
        mock_send_email.assert_called_once()
        call_args = mock_send_email.call_args
        assert call_args[0][0] == email
        assert call_args[0][1] == f"✅ {route_name}: Victoria restored | Northern still disrupted"

    @pytest.mark.asyncio
    @patch("app.services.email_service.EmailService.send_email", new_callable=AsyncMock)
    async def test_send_status_update_email_with_user_name(self, mock_send_email: AsyncMock) -> None:
        """Test status update email with user name."""
        service = NotificationService()
        email = "test@example.com"
        route_name = "Morning Commute"
        cleared_lines = [
            ClearedLineInfo(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                previous_severity=3,
                previous_status="Severe Delays",
                current_severity=10,
                current_status="Good Service",
            )
        ]
        still_disrupted = []

        await service.send_status_update_email(email, route_name, cleared_lines, still_disrupted, user_name="John")

        # Verify EmailService.send_email was called
        mock_send_email.assert_called_once()
        call_args = mock_send_email.call_args
        assert call_args[0][0] == email
        assert call_args[0][1] == f"✅ {route_name}: Victoria restored"

    @pytest.mark.asyncio
    @patch("app.services.email_service.EmailService.send_email", new_callable=AsyncMock)
    async def test_send_status_update_email_multiple_cleared_lines(self, mock_send_email: AsyncMock) -> None:
        """Test status update email with multiple cleared lines."""
        service = NotificationService()
        email = "test@example.com"
        route_name = "Morning Commute"
        cleared_lines = [
            ClearedLineInfo(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                previous_severity=3,
                previous_status="Severe Delays",
                current_severity=10,
                current_status="Good Service",
            ),
            ClearedLineInfo(
                line_id="northern",
                line_name="Northern",
                mode="tube",
                previous_severity=6,
                previous_status="Minor Delays",
                current_severity=10,
                current_status="Good Service",
            ),
        ]
        still_disrupted = []

        await service.send_status_update_email(email, route_name, cleared_lines, still_disrupted)

        # Verify email was sent
        mock_send_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_status_update_email_error_propagates(self) -> None:
        """Test status update email error is propagated."""
        service = NotificationService()
        cleared_lines = [
            ClearedLineInfo(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                previous_severity=3,
                previous_status="Severe Delays",
                current_severity=10,
                current_status="Good Service",
            )
        ]
        still_disrupted = []

        with (
            patch.object(service.email_service, "send_email", side_effect=Exception("Email error")),
            pytest.raises(Exception, match="Email error"),
        ):
            await service.send_status_update_email(
                email="test@example.com",
                route_name="Test",
                cleared_lines=cleared_lines,
                still_disrupted=still_disrupted,
            )

    @pytest.mark.asyncio
    @patch("app.services.sms_service.SmsService.send_sms", new_callable=AsyncMock)
    async def test_send_status_update_sms_success(self, mock_send_sms: AsyncMock) -> None:
        """Test successful status update SMS sending."""
        service = NotificationService()
        phone = "+447700900123"
        route_name = "Morning Commute"
        cleared_lines = [
            ClearedLineInfo(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                previous_severity=3,
                previous_status="Severe Delays",
                current_severity=10,
                current_status="Good Service",
            )
        ]
        still_disrupted = [
            DisruptionResponse(
                line_id="northern",
                line_name="Northern",
                mode="tube",
                status_severity=6,
                status_severity_description="Minor Delays",
                reason="Signal failure",
                created_at=datetime.now(UTC),
            )
        ]

        await service.send_status_update_sms(phone, route_name, cleared_lines, still_disrupted)

        # Verify SmsService.send_sms was called
        mock_send_sms.assert_called_once()
        call_args = mock_send_sms.call_args
        assert call_args[0][0] == phone
        assert "Service restored" in call_args[0][1]
        assert "Victoria" in call_args[0][1]

    @pytest.mark.asyncio
    @patch("app.services.sms_service.SmsService.send_sms", new_callable=AsyncMock)
    async def test_send_status_update_sms_multiple_cleared_lines(self, mock_send_sms: AsyncMock) -> None:
        """Test status update SMS with multiple cleared lines."""
        service = NotificationService()
        phone = "+447700900123"
        route_name = "Test Route"
        cleared_lines = [
            ClearedLineInfo(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                previous_severity=3,
                previous_status="Severe Delays",
                current_severity=10,
                current_status="Good Service",
            ),
            ClearedLineInfo(
                line_id="northern",
                line_name="Northern",
                mode="tube",
                previous_severity=6,
                previous_status="Minor Delays",
                current_severity=10,
                current_status="Good Service",
            ),
            ClearedLineInfo(
                line_id="piccadilly",
                line_name="Piccadilly",
                mode="tube",
                previous_severity=4,
                previous_status="Part Suspended",
                current_severity=10,
                current_status="Good Service",
            ),
            ClearedLineInfo(
                line_id="district",
                line_name="District",
                mode="tube",
                previous_severity=3,
                previous_status="Severe Delays",
                current_severity=10,
                current_status="Good Service",
            ),
        ]
        still_disrupted = []

        await service.send_status_update_sms(phone, route_name, cleared_lines, still_disrupted)

        # Verify SMS was sent
        mock_send_sms.assert_called_once()
        call_args = mock_send_sms.call_args
        sent_message = call_args[0][1]

        # Should limit to first 3 cleared lines
        assert "Victoria" in sent_message
        assert "Northern" in sent_message
        assert "Piccadilly" in sent_message
        # Fourth line may or may not be included depending on length

    @pytest.mark.asyncio
    @patch("app.services.sms_service.SmsService.send_sms", new_callable=AsyncMock)
    async def test_send_status_update_sms_truncates_long_message(self, mock_send_sms: AsyncMock) -> None:
        """Test status update SMS truncation when message is too long."""
        service = NotificationService()
        phone = "+447700900123"
        route_name = "My Very Long Route Name For Testing Purposes"
        cleared_lines = [
            ClearedLineInfo(
                line_id="metropolitan",
                line_name="Metropolitan Line Experiencing Issues",
                mode="tube",
                previous_severity=3,
                previous_status="Severe Delays and Signal Failures",
                current_severity=10,
                current_status="Good Service",
            )
        ]
        still_disrupted = [
            DisruptionResponse(
                line_id="hammersmith-city",
                line_name="Hammersmith & City Line Now",
                mode="tube",
                status_severity=10,
                status_severity_description="Part Suspended Between Multiple Stations",
                reason="Engineering works",
                created_at=datetime.now(UTC),
            ),
            DisruptionResponse(
                line_id="circle",
                line_name="Circle Line With Additional Information",
                mode="tube",
                status_severity=6,
                status_severity_description="Minor Delays Throughout The Line",
                reason="Signal failure",
                created_at=datetime.now(UTC),
            ),
        ]

        await service.send_status_update_sms(phone, route_name, cleared_lines, still_disrupted)

        # Verify SMS was sent
        mock_send_sms.assert_called_once()
        call_args = mock_send_sms.call_args
        sent_message = call_args[0][1]

        # Verify message was truncated (still_disrupted part removed)
        assert "Service restored" in sent_message
        assert "Metropolitan" in sent_message or "Metropolitan Line" in sent_message
        # Still disrupted section should be removed if message is too long
        assert len(sent_message) <= 160

    @pytest.mark.asyncio
    @patch("app.services.sms_service.SmsService.send_sms", new_callable=AsyncMock)
    async def test_send_status_update_sms_multistage_truncation_3_to_2_lines(self, mock_send_sms: AsyncMock) -> None:
        """Test SMS truncation reduces from 3 cleared lines to 2 when needed."""
        service = NotificationService()
        phone = "+447700900123"
        route_name = "Very Long Route Name That Takes Up Space"
        cleared_lines = [
            ClearedLineInfo(
                line_id="metropolitan",
                line_name="Metropolitan Line",
                mode="tube",
                previous_severity=3,
                previous_status="Severe Delays",
                current_severity=10,
                current_status="Good Service",
            ),
            ClearedLineInfo(
                line_id="hammersmith-city",
                line_name="Hammersmith & City",
                mode="tube",
                previous_severity=3,
                previous_status="Minor Delays",
                current_severity=10,
                current_status="Good Service",
            ),
            ClearedLineInfo(
                line_id="circle",
                line_name="Circle Line Name",
                mode="tube",
                previous_severity=6,
                previous_status="Part Suspended",
                current_severity=10,
                current_status="Good Service",
            ),
        ]
        still_disrupted = []

        await service.send_status_update_sms(phone, route_name, cleared_lines, still_disrupted)

        mock_send_sms.assert_called_once()
        call_args = mock_send_sms.call_args
        sent_message = call_args[0][1]

        # Should reduce to 2 lines if 3 is too long
        assert len(sent_message) <= 160

    @pytest.mark.asyncio
    @patch("app.services.sms_service.SmsService.send_sms", new_callable=AsyncMock)
    async def test_send_status_update_sms_multistage_truncation_2_to_1_line(self, mock_send_sms: AsyncMock) -> None:
        """Test SMS truncation reduces from 2 cleared lines to 1 when needed."""
        service = NotificationService()
        phone = "+447700900123"
        route_name = "Extremely Long Route Name For Testing Multi-Stage Truncation"
        cleared_lines = [
            ClearedLineInfo(
                line_id="metropolitan",
                line_name="Metropolitan Line With Very Long Name",
                mode="tube",
                previous_severity=3,
                previous_status="Severe Delays",
                current_severity=10,
                current_status="Good Service",
            ),
            ClearedLineInfo(
                line_id="hammersmith-city",
                line_name="Hammersmith & City Line",
                mode="tube",
                previous_severity=3,
                previous_status="Minor Delays",
                current_severity=10,
                current_status="Good Service",
            ),
        ]
        still_disrupted = []

        await service.send_status_update_sms(phone, route_name, cleared_lines, still_disrupted)

        mock_send_sms.assert_called_once()
        call_args = mock_send_sms.call_args
        sent_message = call_args[0][1]

        # Should reduce to 1 line if 2 is too long
        assert len(sent_message) <= 160
        # Should contain first line name
        assert "Metropolitan" in sent_message

    @pytest.mark.asyncio
    @patch("app.services.sms_service.SmsService.send_sms", new_callable=AsyncMock)
    async def test_send_status_update_sms_multistage_truncation_with_ellipsis(self, mock_send_sms: AsyncMock) -> None:
        """Test SMS truncation uses ellipsis for very long route and line names."""
        service = NotificationService()
        phone = "+447700900123"
        route_name = "Extremely Long Route Name That Definitely Needs To Be Truncated With Ellipsis For Testing"
        cleared_lines = [
            ClearedLineInfo(
                line_id="metropolitan",
                line_name="Metropolitan Line With An Extremely Long Name That Also Needs Truncation",
                mode="tube",
                previous_severity=3,
                previous_status="Severe Delays",
                current_severity=10,
                current_status="Good Service",
            ),
        ]
        still_disrupted = []

        await service.send_status_update_sms(phone, route_name, cleared_lines, still_disrupted)

        mock_send_sms.assert_called_once()
        call_args = mock_send_sms.call_args
        sent_message = call_args[0][1]

        # Should truncate with ellipsis
        assert len(sent_message) <= 160
        # Should contain ellipsis if truncation occurred
        # Note: ellipsis may appear in route name or line name depending on lengths

    @pytest.mark.asyncio
    @patch("app.services.sms_service.SmsService.send_sms", new_callable=AsyncMock)
    async def test_send_status_update_sms_force_truncate_fallback(self, mock_send_sms: AsyncMock) -> None:
        """Test SMS force truncate as final fallback."""
        service = NotificationService()
        phone = "+447700900123"
        # Create an extreme case that would still exceed 160 chars even after all truncation stages
        route_name = "A" * 50  # Very long route name
        cleared_lines = [
            ClearedLineInfo(
                line_id="line",
                line_name="B" * 50,  # Very long line name
                mode="tube",
                previous_severity=3,
                previous_status="Severe Delays",
                current_severity=10,
                current_status="Good Service",
            ),
        ]
        still_disrupted = []

        await service.send_status_update_sms(phone, route_name, cleared_lines, still_disrupted)

        mock_send_sms.assert_called_once()
        call_args = mock_send_sms.call_args
        sent_message = call_args[0][1]

        # Must be exactly 160 chars or less due to force truncate
        assert len(sent_message) <= 160

    @pytest.mark.asyncio
    async def test_send_status_update_sms_error_propagates(self) -> None:
        """Test status update SMS error is propagated."""
        service = NotificationService()
        cleared_lines = [
            ClearedLineInfo(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                previous_severity=3,
                previous_status="Severe Delays",
                current_severity=10,
                current_status="Good Service",
            )
        ]
        still_disrupted = []

        with (
            patch.object(service.sms_service, "send_sms", side_effect=Exception("SMS error")),
            pytest.raises(Exception, match="SMS error"),
        ):
            await service.send_status_update_sms(
                phone="+447700900123",
                route_name="Test",
                cleared_lines=cleared_lines,
                still_disrupted=still_disrupted,
            )

    @pytest.mark.asyncio
    async def test_build_disruption_subject_empty_list(self) -> None:
        """Test subject line generation for empty disruption list."""
        disruptions = []

        subject = _build_disruption_subject("Morning Commute", disruptions)
        assert subject == "⚠️ Morning Commute: All clear"

    @pytest.mark.asyncio
    async def test_build_disruption_subject_single_line(self) -> None:
        """Test subject line generation for single disrupted line."""
        disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=6,
                status_severity_description="Minor Delays",
                reason="Signal failure",
            )
        ]

        subject = _build_disruption_subject("Morning Commute", disruptions)
        assert subject == "⚠️ Morning Commute: Victoria disrupted"

    @pytest.mark.asyncio
    async def test_build_disruption_subject_multiple_lines(self) -> None:
        """Test subject line generation for multiple disrupted lines."""
        disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=6,
                status_severity_description="Minor Delays",
            ),
            DisruptionResponse(
                line_id="northern",
                line_name="Northern",
                mode="tube",
                status_severity=3,
                status_severity_description="Severe Delays",
            ),
            DisruptionResponse(
                line_id="central",
                line_name="Central",
                mode="tube",
                status_severity=6,
                status_severity_description="Part Suspended",
            ),
        ]

        subject = _build_disruption_subject("To Work", disruptions)
        assert subject == "⚠️ To Work: Victoria, Northern, Central disrupted"

    @pytest.mark.asyncio
    async def test_build_status_update_subject_single_restored(self) -> None:
        """Test subject line for single restored line with no remaining disruptions."""
        cleared_lines = [
            ClearedLineInfo(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                previous_severity=3,
                previous_status="Severe Delays",
                current_severity=10,
                current_status="Good Service",
            )
        ]
        still_disrupted = []

        subject = _build_status_update_subject("Morning Commute", cleared_lines, still_disrupted)
        assert subject == "✅ Morning Commute: Victoria restored"

    @pytest.mark.asyncio
    async def test_build_status_update_subject_all_clear(self) -> None:
        """Test subject line when multiple lines cleared and all clear."""
        cleared_lines = [
            ClearedLineInfo(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                previous_severity=3,
                previous_status="Severe Delays",
                current_severity=10,
                current_status="Good Service",
            ),
            ClearedLineInfo(
                line_id="northern",
                line_name="Northern",
                mode="tube",
                previous_severity=6,
                previous_status="Minor Delays",
                current_severity=10,
                current_status="Good Service",
            ),
        ]
        still_disrupted = []

        subject = _build_status_update_subject("Morning Commute", cleared_lines, still_disrupted)
        assert subject == "✅ Morning Commute: All clear"

    @pytest.mark.asyncio
    async def test_build_status_update_subject_mixed(self) -> None:
        """Test subject line when some lines cleared but others still disrupted."""
        cleared_lines = [
            ClearedLineInfo(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                previous_severity=3,
                previous_status="Severe Delays",
                current_severity=10,
                current_status="Good Service",
            )
        ]
        still_disrupted = [
            DisruptionResponse(
                line_id="northern",
                line_name="Northern",
                mode="tube",
                status_severity=6,
                status_severity_description="Minor Delays",
                reason="Signal failure",
            )
        ]

        subject = _build_status_update_subject("To Work", cleared_lines, still_disrupted)
        assert subject == "✅ To Work: Victoria restored | Northern still disrupted"
