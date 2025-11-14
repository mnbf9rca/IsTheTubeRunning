"""Email service for sending verification and notification emails."""

import asyncio
import functools
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

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

    async def send_email(
        self,
        to: str,
        subject: str,
        html_content: str,
        text_content: str,
    ) -> None:
        """
        Send a generic email with HTML and plain text content.

        Uses run_in_executor to prevent blocking the event loop during SMTP operations.

        Args:
            to: Recipient email address
            subject: Email subject line
            html_content: HTML content of the email
            text_content: Plain text fallback content

        Raises:
            smtplib.SMTPException: If email sending fails
        """
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            functools.partial(
                self._send_email_sync,
                to,
                subject,
                html_content,
                text_content,
            ),
        )

    async def send_verification_email(self, email: str, code: str) -> None:
        """
        Send a verification email with the provided code.

        Uses run_in_executor to prevent blocking the event loop during SMTP operations.

        Args:
            email: Recipient email address
            code: 6-digit verification code

        Raises:
            smtplib.SMTPException: If email sending fails
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

    def _send_email_sync(
        self,
        to: str,
        subject: str,
        html_content: str,
        text_content: str,
    ) -> None:
        """
        Synchronously send an email (runs in thread pool).

        This method contains all blocking I/O operations (SMTP).

        Args:
            to: Recipient email address
            subject: Email subject line
            html_content: HTML content of the email
            text_content: Plain text fallback content

        Raises:
            smtplib.SMTPException: If email sending fails
        """
        try:
            # Create the email message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = self.from_email
            message["To"] = to

            # Attach parts (plain text first, then HTML)
            part1 = MIMEText(text_content, "plain")
            part2 = MIMEText(html_content, "html")
            message.attach(part1)
            message.attach(part2)

            # Send the email via SMTP (blocking network I/O)
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(message)

            logger.info("email_sent", recipient=to, subject=subject)

        except smtplib.SMTPException as e:
            logger.error("email_send_failed", recipient=to, subject=subject, error=str(e))
            raise
