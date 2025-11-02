"""SMS service stub for logging verification codes."""

import asyncio
import functools
from datetime import UTC, datetime
from pathlib import Path

import structlog

from app.core.config import settings

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

    async def send_verification_sms(self, phone: str, code: str) -> None:
        """
        Send a verification SMS with the provided code.

        Currently logs to console and file instead of sending actual SMS.
        Uses run_in_executor to prevent blocking the event loop during file I/O.

        Args:
            phone: Recipient phone number
            code: 6-digit verification code
        """
        timestamp = datetime.now(UTC).isoformat()
        message = f"Your IsTheTubeRunning verification code is: {code}. This code expires in 15 minutes."

        # Log to structured logger (console) - non-blocking
        logger.info(
            "verification_sms_sent",
            recipient=phone,
            code=code,
            message=message,
            timestamp=timestamp,
        )

        # Log to file asynchronously (runs in thread pool)
        if SMS_LOG_FILE:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                functools.partial(self._write_to_file_sync, phone, code, message, timestamp),
            )

    def _write_to_file_sync(self, phone: str, code: str, message: str, timestamp: str) -> None:
        """
        Synchronously write SMS log entry to file (runs in thread pool).

        Args:
            phone: Recipient phone number
            code: Verification code
            message: Full SMS message
            timestamp: ISO format timestamp
        """
        if not SMS_LOG_FILE:
            return

        try:
            log_entry = f"[{timestamp}] TO: {phone} | CODE: {code} | MESSAGE: {message}\n"
            with SMS_LOG_FILE.open("a") as f:
                f.write(log_entry)
        except OSError as e:
            logger.error(
                "sms_file_logging_failed",
                error=str(e),
                recipient=phone,
            )
