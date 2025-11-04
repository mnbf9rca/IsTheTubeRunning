"""Notification service for sending disruption alerts via email and SMS."""

import asyncio
import functools
import smtplib
from datetime import UTC, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.schemas.tfl import DisruptionResponse
from app.services.email_service import EmailService
from app.services.sms_service import SMS_LOG_FILE, SmsService

logger = structlog.get_logger(__name__)

# SMS character limit constant
SMS_MAX_LENGTH = 160

# Initialize Jinja2 environment for email templates
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


class NotificationService:
    """Service for sending disruption notifications via email and SMS."""

    def __init__(self) -> None:
        """Initialize the notification service with email and SMS services."""
        self.email_service = EmailService()
        self.sms_service = SmsService()

    async def send_disruption_email(
        self,
        email: str,
        route_name: str,
        disruptions: list[DisruptionResponse],
        user_name: str | None = None,
    ) -> None:
        """
        Send a disruption alert email.

        Uses run_in_executor to prevent blocking the event loop during SMTP operations.

        Args:
            email: Recipient email address
            route_name: Name of the route affected
            disruptions: List of disruptions affecting the route
            user_name: User's name for personalized greeting (defaults to "there")

        Raises:
            Exception: If email sending fails
        """
        try:
            # Build email subject
            subject = f"⚠️ Disruption Alert: {route_name}"

            # Render the HTML template
            html_content = self._render_email_template(
                "email/disruption_alert.html",
                {
                    "route_name": route_name,
                    "user_name": user_name,
                    "disruptions": disruptions,
                    "tfl_status_url": "https://tfl.gov.uk/tube-dlr-overground/status/",
                },
            )

            # Send email asynchronously
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                functools.partial(
                    self._send_email_sync,
                    email,
                    subject,
                    html_content,
                    route_name,
                    disruptions,
                ),
            )

            logger.info(
                "disruption_email_sent",
                recipient=email,
                route_name=route_name,
                disruption_count=len(disruptions),
            )

        except Exception as e:
            logger.error(
                "disruption_email_failed",
                recipient=email,
                route_name=route_name,
                error=str(e),
                exc_info=e,
            )
            raise

    def _send_email_sync(
        self,
        email: str,
        subject: str,
        html_content: str,
        route_name: str,
        disruptions: list[DisruptionResponse],
    ) -> None:
        """
        Synchronously send a disruption alert email (runs in thread pool).

        This method contains all blocking I/O operations (SMTP).

        Args:
            email: Recipient email address
            subject: Email subject line
            html_content: Rendered HTML content
            route_name: Name of the route (for plain text fallback)
            disruptions: List of disruptions (for plain text fallback)

        Raises:
            Exception: If email sending fails
        """
        try:
            # Create the email message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = self.email_service.from_email
            message["To"] = email

            # Create plain text fallback
            text_content = f"""
Disruption Alert: {route_name}

The following disruptions are affecting your route:

"""
            for disruption in disruptions:
                text_content += f"- {disruption.line_name}: {disruption.status_severity_description}\n"
                if disruption.reason:
                    text_content += f"  Reason: {disruption.reason}\n"

            text_content += """
For the latest updates, visit: https://tfl.gov.uk/tube-dlr-overground/status/

This is an automated alert from IsTheTubeRunning.
© 2025 IsTheTubeRunning. All rights reserved.
            """.strip()

            # Attach parts
            part1 = MIMEText(text_content, "plain")
            part2 = MIMEText(html_content, "html")
            message.attach(part1)
            message.attach(part2)

            # Send the email via SMTP (blocking network I/O)
            with smtplib.SMTP(
                self.email_service.smtp_host,
                self.email_service.smtp_port,
            ) as server:
                server.starttls()
                server.login(
                    self.email_service.smtp_user,
                    self.email_service.smtp_password,
                )
                server.send_message(message)

        except Exception as e:
            logger.error(
                "smtp_send_failed",
                recipient=email,
                error=str(e),
            )
            raise

    async def send_disruption_sms(
        self,
        phone: str,
        route_name: str,
        disruptions: list[DisruptionResponse],
    ) -> None:
        """
        Send a disruption alert SMS.

        Creates a concise SMS message (under 160 characters when possible)
        and sends via SmsService.

        Args:
            phone: Recipient phone number
            route_name: Name of the route affected
            disruptions: List of disruptions affecting the route
        """
        try:
            # Create concise SMS text (SMS has character limits)
            # Format: "TfL Alert: {route_name} affected. {line_name}: {status}."

            # Start with base message
            base_msg = f"TfL Alert: {route_name} affected. "

            # Add first 2-3 disruptions (prioritize fitting in 160 chars)
            disruption_parts = []
            for disruption in disruptions[:3]:  # Limit to first 3 disruptions
                part = f"{disruption.line_name}: {disruption.status_severity_description}"
                disruption_parts.append(part)

            disruption_text = ". ".join(disruption_parts[:2])  # Start with first 2

            # Add URL
            url = "More: tfl.gov.uk/tube-dlr-overground/status/"

            # Build final message
            message = f"{base_msg}{disruption_text}. {url}"

            # If too long and we have multiple disruptions, try with just one
            if len(message) > SMS_MAX_LENGTH and len(disruptions) > 1:
                disruption_text = disruption_parts[0]
                message = f"{base_msg}{disruption_text}. {url}"

            # Send SMS via SmsService (which logs to file/console for now)
            await self._send_sms_async(phone, message)

            logger.info(
                "disruption_sms_sent",
                recipient=phone,
                route_name=route_name,
                disruption_count=len(disruptions),
                message_length=len(message),
            )

        except Exception as e:
            logger.error(
                "disruption_sms_failed",
                recipient=phone,
                route_name=route_name,
                error=str(e),
                exc_info=e,
            )
            raise

    async def _send_sms_async(self, phone: str, message: str) -> None:
        """
        Send SMS message asynchronously via SmsService.

        Args:
            phone: Recipient phone number
            message: SMS message content
        """
        timestamp = datetime.now(UTC).isoformat()

        # Log to structured logger
        logger.info(
            "sms_message_sending",
            recipient=phone,
            message=message,
            timestamp=timestamp,
        )

        # Use SmsService's file logging functionality
        # Since SmsService doesn't have a generic send method, we'll use run_in_executor
        # to write directly to file similar to send_verification_sms
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            functools.partial(
                self._write_sms_log_sync,
                phone,
                message,
                timestamp,
            ),
        )

    def _write_sms_log_sync(self, phone: str, message: str, timestamp: str) -> None:
        """
        Synchronously write SMS log entry to file (runs in thread pool).

        Args:
            phone: Recipient phone number
            message: SMS message content
            timestamp: ISO format timestamp
        """
        if not SMS_LOG_FILE:
            return

        try:
            log_entry = f"[{timestamp}] TO: {phone} | MESSAGE: {message}\n"
            with SMS_LOG_FILE.open("a") as f:
                f.write(log_entry)
        except OSError as e:
            logger.error(
                "sms_file_logging_failed",
                error=str(e),
                recipient=phone,
            )

    def _render_email_template(self, template_name: str, context: dict[str, Any]) -> str:
        """
        Render an email template with the given context.

        Args:
            template_name: Name of the template file (e.g., "email/disruption_alert.html")
            context: Dictionary of variables to pass to the template

        Returns:
            Rendered HTML string

        Raises:
            jinja2.TemplateNotFound: If template file doesn't exist
        """
        try:
            template = jinja_env.get_template(template_name)
            return template.render(context)
        except Exception as e:
            logger.error(
                "template_rendering_failed",
                template_name=template_name,
                error=str(e),
                exc_info=e,
            )
            raise
