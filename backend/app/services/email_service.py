"""Email service for sending verification and notification emails."""

from email.message import EmailMessage
from pathlib import Path

import aiosmtplib
import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape
from opentelemetry.trace import SpanKind

from app.core.config import require_config, settings
from app.core.telemetry import service_span
from app.utils.pii import hash_pii

# Validate required email configuration
require_config("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM_EMAIL")

logger = structlog.get_logger(__name__)

# Standard SMTP port for implicit TLS (SMTPS)
SMTPS_PORT = 465


def get_tls_settings(port: int, require_tls: bool) -> tuple[bool, bool | None]:
    """
    Determine TLS settings based on port and require_tls flag.

    Args:
        port: SMTP port number
        require_tls: Whether to require STARTTLS upgrade on non-465 ports

    Returns:
        Tuple of (use_tls, start_tls) for aiosmtplib.SMTP
    """
    """
    from https://aiosmtplib.readthedocs.io/en/stable/encryption.html and the signature of aiosmtplib.SMTP:

    | Port | Type         | REQUIRE_TLS | use_tls | start_tls | Behavior                             |
    |------|--------------|-------------|---------|-----------|--------------------------------------|
    | 25   | Plaintext    | False       | False   | None      | Auto-upgrade if available            |
    | 25   | Plaintext    | True        | False   | True      | Force upgrade, fail if not supported |
    | 465  | Implicit TLS | False       | True    | N/A       | Always TLS (port behavior)           |
    | 465  | Implicit TLS | True        | True    | N/A       | Always TLS (port behavior)           |
    | 587  | STARTTLS     | False       | False   | None      | Auto-upgrade if available            |
    | 587  | STARTTLS     | True        | False   | True      | Force upgrade, fail if not supported |

    So the logic:
    - Port 465: use_tls=True (always, regardless of REQUIRE_TLS)
    - Other ports: use_tls=False, start_tls=True if REQUIRE_TLS else None

    This way REQUIRE_TLS controls whether we require the STARTTLS upgrade to succeed on ports 25/587.

    """

    if port == SMTPS_PORT:
        return (True, None)  # Implicit TLS, start_tls N/A
    return (False, True if require_tls else None)


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
        self.require_tls = settings.SMTP_REQUIRE_TLS

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
        logger.info(
            "verification_email_sent",
            recipient_hash=hash_pii(email),
            code_length=len(code),
        )

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
            asyncio.TimeoutError: If SMTP operation times out
            OSError: If network/socket errors occur
        """
        # Compute hash once for use in logs and telemetry
        recipient_hash = hash_pii(to)

        with service_span(
            "email.send",
            "smtp",
            kind=SpanKind.CLIENT,
        ) as span:
            # Set SMTP span attributes
            span.set_attribute("smtp.host", self.smtp_host)
            span.set_attribute("smtp.port", self.smtp_port)
            span.set_attribute("email.recipient_hash", recipient_hash)
            span.set_attribute("email.subject", subject)
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
                use_tls, start_tls = get_tls_settings(self.smtp_port, self.require_tls)

                async with aiosmtplib.SMTP(
                    hostname=self.smtp_host,
                    port=self.smtp_port,
                    timeout=self.smtp_timeout,
                    use_tls=use_tls,
                    start_tls=start_tls,
                ) as server:
                    await server.login(self.smtp_user, self.smtp_password)
                    await server.send_message(message)

                logger.info("email_sent", recipient_hash=recipient_hash, subject=subject)

            except TimeoutError as e:
                logger.error(
                    "email_send_timeout",
                    recipient_hash=recipient_hash,
                    subject=subject,
                    error=str(e),
                )
                raise
            except OSError as e:
                # Catches ConnectionRefusedError, ConnectionResetError, socket errors, etc.
                logger.error(
                    "email_send_network_error",
                    recipient_hash=recipient_hash,
                    subject=subject,
                    error=str(e),
                )
                raise
            except aiosmtplib.SMTPException as e:
                logger.error(
                    "email_send_failed",
                    recipient_hash=recipient_hash,
                    subject=subject,
                    error=str(e),
                )
                raise
