"""SMS service stub for logging verification codes."""

import os
from datetime import UTC, datetime
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

# SMS log file location
# Use temp directory in tests to avoid permission issues
SMS_LOG_DIR = Path("/tmp") if os.getenv("DEBUG") == "true" else Path()
SMS_LOG_FILE = SMS_LOG_DIR / "sms_log.txt"


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

        Args:
            phone: Recipient phone number
            code: 6-digit verification code
        """
        timestamp = datetime.now(UTC).isoformat()
        message = f"Your IsTheTubeRunning verification code is: {code}. This code expires in 15 minutes."

        # Log to structured logger (console)
        logger.info(
            "verification_sms_sent",
            recipient=phone,
            code=code,
            message=message,
            timestamp=timestamp,
        )

        # Log to file
        self._write_to_file(phone, code, message, timestamp)

    def _write_to_file(self, phone: str, code: str, message: str, timestamp: str) -> None:
        """
        Write SMS log entry to file.

        Args:
            phone: Recipient phone number
            code: Verification code
            message: Full SMS message
            timestamp: ISO format timestamp
        """
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
