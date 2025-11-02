"""Email service for sending verification and notification emails."""

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
template_dir = Path(__file__).parent.parent / "templates" / "email"
jinja_env = Environment(
    loader=FileSystemLoader(str(template_dir)),
    autoescape=select_autoescape(["html", "xml"]),
)


class EmailService:
    """Service for sending emails via SMTP."""

    def __init__(self) -> None:
        """Initialize the email service."""
        self.smtp_host: str = settings.SMTP_HOST  # type: ignore[assignment]
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user: str = settings.SMTP_USER  # type: ignore[assignment]
        self.smtp_password: str = settings.SMTP_PASSWORD  # type: ignore[assignment]
        self.from_email: str = settings.SMTP_FROM_EMAIL  # type: ignore[assignment]

    async def send_verification_email(self, email: str, code: str) -> None:
        """
        Send a verification email with the provided code.

        Args:
            email: Recipient email address
            code: 6-digit verification code

        Raises:
            smtplib.SMTPException: If email sending fails
        """
        try:
            # Render the HTML template
            template = jinja_env.get_template("verification.html")
            html_content = template.render(code=code, contact_type="email address")

            # Create the email message
            message = MIMEMultipart("alternative")
            message["Subject"] = "Verify Your Email - IsTheTubeRunning"
            message["From"] = self.from_email
            message["To"] = email

            # Add plain text fallback
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

            # Attach parts
            part1 = MIMEText(text_content, "plain")
            part2 = MIMEText(html_content, "html")
            message.attach(part1)
            message.attach(part2)

            # Send the email via SMTP
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(message)

            logger.info(
                "verification_email_sent",
                recipient=email,
                code_length=len(code),
            )

        except smtplib.SMTPException as e:
            logger.error(
                "verification_email_failed",
                recipient=email,
                error=str(e),
            )
            raise
