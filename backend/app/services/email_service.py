"""Email service for sending verification and notification emails."""

from email.message import EmailMessage
from pathlib import Path

import aiosmtplib
import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import require_config, settings

# Validate required email configuration
require_config("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM_EMAIL")

logger = structlog.get_logger(__name__)

# Initialize Jinja2 environment for email templates
# Security: Using autoescape with select_autoescape for HTML/XML provides XSS protection
# by automatically escaping all variables in templates. This is equivalent to Flask's
# render_template() security model. Template variables (code, contact_type) are always
# escaped, preventing injection attacks.
template_dir = Path(__file__).parent.parent / "templates" / "email"
jinja_env = Environment(
    loader=FileSystemLoader(str(template_dir)),
    autoescape=select_autoescape(["html", "xml"]),
)


class EmailService:
    """Service for sending emails via SMTP."""

    def __init__(self) -> None:
        """Initialize the email service.

        Note: All required fields are validated by require_config() at module import time.
        The assert statements narrow types for mypy after validation.
        """
        # Type narrowing: require_config() guarantees these are not None
        assert settings.SMTP_HOST is not None
        assert settings.SMTP_USER is not None
        assert settings.SMTP_PASSWORD is not None
        assert settings.SMTP_FROM_EMAIL is not None

        self.smtp_host: str = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user: str = settings.SMTP_USER
        self.smtp_password: str = settings.SMTP_PASSWORD
        self.from_email: str = settings.SMTP_FROM_EMAIL
        self.smtp_timeout = settings.SMTP_TIMEOUT

    async def send_email(
        self,
        to: str,
        subject: str,
        html_content: str,
        text_content: str,
    ) -> None:
        """
        Send a generic email with HTML and plain text content.

        This is a truly async method using aiosmtplib for non-blocking SMTP operations.

        Args:
            to: Recipient email address
            subject: Email subject line
            html_content: HTML content of the email
            text_content: Plain text fallback content

        Raises:
            aiosmtplib.SMTPException: If email sending fails
        """
        await self._send_email_async(to, subject, html_content, text_content)

    async def send_verification_email(self, email: str, code: str) -> None:
        """
        Send a verification email with the provided code.

        This is a truly async method using aiosmtplib for non-blocking SMTP operations.

        Args:
            email: Recipient email address
            code: 6-digit verification code

        Raises:
            aiosmtplib.SMTPException: If email sending fails
        """
        # Render the HTML template
        template = jinja_env.get_template("verification.html")
        html_content = template.render(code=code, contact_type="email address")

        # Create plain text fallback
        text_content = f"""
Hello,

Thank you for signing up! Please use the verification code below to verify your email address:

{code}

This code expires in 15 minutes.

If you didn't request this verification code, you can safely ignore this email.
For security reasons, do not share this code with anyone.

This is an automated message from IsTheTubeRunning.
© 2025 IsTheTubeRunning. All rights reserved.
        """.strip()

        subject = "Verify Your Email - IsTheTubeRunning"

        # Use generic send_email method
        await self.send_email(email, subject, html_content, text_content)
        logger.info("verification_email_sent", recipient=email, code_length=len(code))

    async def _send_email_async(
        self,
        to: str,
        subject: str,
        html_content: str,
        text_content: str,
    ) -> None:
        """
        Asynchronously send an email using aiosmtplib.

        This method performs truly async SMTP operations without blocking the event loop.

        Args:
            to: Recipient email address
            subject: Email subject line
            html_content: HTML content of the email
            text_content: Plain text fallback content

        Raises:
            aiosmtplib.SMTPException: If email sending fails
        """
        try:
            # Create the email message
            message = EmailMessage()
            message["Subject"] = subject
            message["From"] = self.from_email
            message["To"] = to

            # Set content (plain text as fallback, HTML as preferred)
            message.set_content(text_content)
            message.add_alternative(html_content, subtype="html")

            # Send the email via SMTP (async network I/O)
            # timeout parameter prevents indefinite hangs on unreachable hosts
            async with aiosmtplib.SMTP(
                hostname=self.smtp_host, port=self.smtp_port, timeout=self.smtp_timeout
            ) as server:
                await server.starttls()
                await server.login(self.smtp_user, self.smtp_password)
                await server.send_message(message)

            logger.info("email_sent", recipient=to, subject=subject)

        except aiosmtplib.SMTPException as e:
            logger.error("email_send_failed", recipient=to, subject=subject, error=str(e))
            raise
