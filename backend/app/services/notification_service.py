"""Notification service for sending disruption alerts via email and SMS."""

import hashlib
from pathlib import Path
from typing import Any

import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.telemetry import service_span
from app.schemas.tfl import DisruptionResponse
from app.services.email_service import EmailService
from app.services.sms_service import SmsService

logger = structlog.get_logger(__name__)

# SMS character limit constant
SMS_MAX_LENGTH = 160


def _hash_recipient(value: str) -> str:
    """
    Hash recipient for span attribute (PII protection).

    Args:
        value: Email or phone number to hash

    Returns:
        First 12 characters of SHA256 hash in lowercase hex
    """
    return hashlib.sha256(value.encode()).hexdigest()[:12]


# Initialize Jinja2 environment for email templates
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
# nosemgrep: python.flask.security.xss.audit.direct-use-of-jinja2
# Justification: autoescape is explicitly enabled with select_autoescape for HTML/XML,
# providing XSS protection. This is a standalone service, not using Flask's render_template.
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

        Uses EmailService for actual email delivery.

        Args:
            email: Recipient email address
            route_name: Name of the route affected
            disruptions: List of disruptions affecting the route
            user_name: User's name for personalized greeting (defaults to "there")

        Raises:
            Exception: If email sending fails
        """
        with service_span(
            "notification.send_disruption_email",
            "notification-service",
        ) as span:
            span.set_attribute("notification.type", "email")
            span.set_attribute("notification.recipient_hash", _hash_recipient(email))
            span.set_attribute("notification.route_name", route_name)
            span.set_attribute("notification.disruption_count", len(disruptions))

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

                # Send email via EmailService
                await self.email_service.send_email(email, subject, html_content, text_content)

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
        with service_span(
            "notification.send_disruption_sms",
            "notification-service",
        ) as span:
            span.set_attribute("notification.type", "sms")
            span.set_attribute("notification.recipient_hash", _hash_recipient(phone))
            span.set_attribute("notification.route_name", route_name)
            span.set_attribute("notification.disruption_count", len(disruptions))

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

                # Set message length as span attribute
                span.set_attribute("notification.message_length", len(message))

                # Send SMS via SmsService
                await self.sms_service.send_sms(phone, message)

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
            # nosemgrep: python.flask.security.xss.audit.direct-use-of-jinja2
            # Justification: Template rendering uses jinja_env with autoescape enabled (line 23-26).
            # All HTML/XML content is automatically escaped, preventing XSS vulnerabilities.
            return template.render(context)
        except Exception as e:
            logger.error(
                "template_rendering_failed",
                template_name=template_name,
                error=str(e),
                exc_info=e,
            )
            raise
