"""SMS service stub for logging verification codes."""

import asyncio
import functools
from datetime import UTC, datetime
from pathlib import Path

import structlog
from opentelemetry.trace import SpanKind

from app.core.config import settings
from app.core.telemetry import service_span
from app.utils.pii import hash_pii

logger = structlog.get_logger(__name__)


def _get_sms_log_file() -> Path | None:
    """
    Get SMS log file path from settings with validation.

    Returns:
        Path to SMS log file if directory is configured and writable, None otherwise
    """
    if not settings.SMS_LOG_DIR:
        logger.warning(
            "sms_file_logging_disabled",
            reason="SMS_LOG_DIR not configured",
        )
        return None

    try:
        log_dir = Path(settings.SMS_LOG_DIR)
        log_dir.mkdir(parents=True, exist_ok=True)

        # Test writeability
        test_file = log_dir / ".write_test"
        test_file.touch()
        test_file.unlink()

        return log_dir / "sms_log.txt"
    except (OSError, PermissionError) as e:
        logger.warning(
            "sms_file_logging_disabled",
            reason=f"SMS_LOG_DIR not writable: {e}",
        )
        return None


SMS_LOG_FILE = _get_sms_log_file()


class SmsService:
    """
    Service for sending SMS messages.

    This is a stub implementation that logs SMS messages to console
    and file instead of actually sending them. This allows development
    and testing without a real SMS provider like Twilio.
    """

    def __init__(self) -> None:
        """Initialize the SMS service."""
        pass

    async def send_sms(self, phone: str, message: str) -> None:
        """
        Send a generic SMS message.

        Currently logs to console and file instead of sending actual SMS.
        Uses run_in_executor to prevent blocking the event loop during file I/O.

        Args:
            phone: Recipient phone number
            message: SMS message content
        """
        with service_span("sms.send", "sms", kind=SpanKind.CLIENT) as span:
            # PII protection: hash the phone number
            phone_hash = hash_pii(phone)
            span.set_attribute("sms.recipient_hash", phone_hash)
            span.set_attribute("sms.message_length", len(message))
            span.set_attribute("sms.stub", True)

            timestamp = datetime.now(UTC).isoformat()

            # Log to structured logger (console) - non-blocking
            logger.info(
                "sms_sent",
                recipient_hash=phone_hash,
                message=message,
                timestamp=timestamp,
            )

            # Log to file asynchronously (runs in thread pool)
            if SMS_LOG_FILE:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(
                    None,
                    functools.partial(self._write_to_file_sync, message, timestamp, phone_hash),
                )

    async def send_verification_sms(self, phone: str, code: str) -> None:
        """
        Send a verification SMS with the provided code.

        Currently logs to console and file instead of sending actual SMS.
        Uses run_in_executor to prevent blocking the event loop during file I/O.

        Args:
            phone: Recipient phone number
            code: 6-digit verification code
        """
        message = f"Your IsTheTubeRunning verification code is: {code}. This code expires in 15 minutes."

        # Compute hash once for use in logs
        phone_hash = hash_pii(phone)

        # Use generic send_sms method
        await self.send_sms(phone, message)
        logger.info("verification_sms_sent", recipient_hash=phone_hash, code=code)

    def _write_to_file_sync(self, message: str, timestamp: str, phone_hash: str) -> None:
        """
        Synchronously write SMS log entry to file (runs in thread pool).

        Args:
            message: Full SMS message
            timestamp: ISO format timestamp
            phone_hash: Pre-computed hash of phone number for logging
        """
        if not SMS_LOG_FILE:
            return

        try:
            log_entry = f"[{timestamp}] TO: {phone_hash} | MESSAGE: {message}\n"
            with SMS_LOG_FILE.open("a") as f:
                f.write(log_entry)
        except OSError as e:
            logger.error(
                "sms_file_logging_failed",
                error=str(e),
                recipient_hash=phone_hash,
            )
