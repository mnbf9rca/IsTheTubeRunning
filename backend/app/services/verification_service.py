"""Verification service for contact verification and rate limiting."""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.telemetry import service_span
from app.models.rate_limit import RateLimitAction, RateLimitLog
from app.models.user import VerificationCode, VerificationType
from app.services.contact_service import get_contact_by_id
from app.services.email_service import EmailService
from app.services.sms_service import SmsService
from app.utils.pii import hash_pii

logger = structlog.get_logger(__name__)

# Rate limiting constants
VERIFICATION_CODE_RATE_LIMIT = 3  # Max codes per contact per hour
ADD_CONTACT_FAILURE_RATE_LIMIT = 5  # Max failed additions per user per 24 hours
VERIFICATION_CODE_EXPIRY_MINUTES = 15
VERIFICATION_CODE_RATE_WINDOW_HOURS = 1
ADD_CONTACT_RATE_WINDOW_HOURS = 24


class VerificationService:
    """Service for managing contact verification and rate limiting."""

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize the verification service.

        Args:
            db: Database session
        """
        self.db = db
        self.email_service = EmailService()
        self.sms_service = SmsService()

    def generate_code(self) -> str:
        """
        Generate a random 6-digit verification code.

        Returns:
            6-digit numeric string
        """
        # Generate a random 6-digit number
        return str(secrets.randbelow(1000000)).zfill(6)

    async def check_verification_rate_limit(self, contact_id: uuid.UUID) -> None:
        """
        Check if verification code request rate limit has been exceeded.

        Args:
            contact_id: UUID of the contact (email or phone)

        Raises:
            HTTPException: 429 if rate limit exceeded
        """
        cutoff_time = datetime.now(UTC) - timedelta(hours=VERIFICATION_CODE_RATE_WINDOW_HOURS)

        # Count verification code requests in the last hour for this contact
        result = await self.db.execute(
            select(func.count())
            .select_from(RateLimitLog)
            .where(
                RateLimitLog.action_type == RateLimitAction.VERIFY_CODE,
                RateLimitLog.resource_id == str(contact_id),
                RateLimitLog.timestamp >= cutoff_time,
            )
        )
        count = result.scalar_one()

        if count >= VERIFICATION_CODE_RATE_LIMIT:
            logger.warning(
                "verification_rate_limit_exceeded",
                contact_id=str(contact_id),
                count=count,
            )
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Too many verification code requests. Please try again in "
                    f"{VERIFICATION_CODE_RATE_WINDOW_HOURS} hour(s)."
                ),
            )

    async def check_add_contact_rate_limit(self, user_id: uuid.UUID) -> None:
        """
        Check if failed contact addition rate limit has been exceeded.

        This prevents enumeration attacks by limiting failed additions.

        Args:
            user_id: UUID of the user

        Raises:
            HTTPException: 429 if rate limit exceeded
        """
        cutoff_time = datetime.now(UTC) - timedelta(hours=ADD_CONTACT_RATE_WINDOW_HOURS)

        # Count failed contact additions in the last 24 hours for this user
        result = await self.db.execute(
            select(func.count())
            .select_from(RateLimitLog)
            .where(
                RateLimitLog.user_id == user_id,
                RateLimitLog.action_type == RateLimitAction.ADD_CONTACT_FAILURE,
                RateLimitLog.timestamp >= cutoff_time,
            )
        )
        count = result.scalar_one()

        if count >= ADD_CONTACT_FAILURE_RATE_LIMIT:
            logger.warning(
                "add_contact_rate_limit_exceeded",
                user_id=str(user_id),
                count=count,
            )
            raise HTTPException(
                status_code=429,
                detail=f"Too many failed attempts. Please try again in {ADD_CONTACT_RATE_WINDOW_HOURS} hours.",
            )

    async def record_verification_code_request(self, contact_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """
        Record a verification code request for rate limiting.

        Args:
            contact_id: UUID of the contact
            user_id: UUID of the user
        """
        log_entry = RateLimitLog(
            user_id=user_id,
            action_type=RateLimitAction.VERIFY_CODE,
            resource_id=str(contact_id),
            timestamp=datetime.now(UTC),
        )
        self.db.add(log_entry)
        await self.db.commit()

    async def record_add_contact_failure(self, user_id: uuid.UUID, contact_value: str) -> None:
        """
        Record a failed contact addition attempt for rate limiting.

        Args:
            user_id: UUID of the user
            contact_value: Email or phone that failed to add
        """
        log_entry = RateLimitLog(
            user_id=user_id,
            action_type=RateLimitAction.ADD_CONTACT_FAILURE,
            resource_id=hash_pii(contact_value),
            timestamp=datetime.now(UTC),
        )
        self.db.add(log_entry)
        await self.db.commit()

    async def reset_verification_rate_limit(self, contact_id: uuid.UUID) -> None:
        """
        Reset verification rate limit for a contact after successful verification.

        Args:
            contact_id: UUID of the contact
        """
        await self.db.execute(
            delete(RateLimitLog).where(
                RateLimitLog.action_type == RateLimitAction.VERIFY_CODE,
                RateLimitLog.resource_id == str(contact_id),
            )
        )
        await self.db.commit()
        logger.info("verification_rate_limit_reset", contact_id=str(contact_id))

    async def create_and_send_code(
        self,
        contact_id: uuid.UUID,
        user_id: uuid.UUID,
        contact_type: VerificationType,
        contact_value: str,
    ) -> None:
        """
        Create a verification code and send it via email or SMS.

        Args:
            contact_id: UUID of the contact
            user_id: UUID of the user
            contact_type: Type of contact (email or SMS)
            contact_value: Email address or phone number

        Raises:
            HTTPException: If rate limit exceeded or sending fails
        """
        with service_span(
            "verification.create_and_send_code",
            "verification-service",
        ) as span:
            # Set span attributes
            span.set_attribute("verification.contact_id", str(contact_id))
            span.set_attribute("verification.user_id", str(user_id))
            span.set_attribute("verification.contact_type", contact_type.value)
            # Check rate limit
            await self.check_verification_rate_limit(contact_id)

            # Generate code
            code = self.generate_code()

            # Create verification code in database
            verification_code = VerificationCode(
                user_id=user_id,
                contact_id=contact_id,
                code=code,
                type=contact_type,
                expires_at=datetime.now(UTC) + timedelta(minutes=VERIFICATION_CODE_EXPIRY_MINUTES),
                used=False,
            )
            self.db.add(verification_code)
            await self.db.commit()

            # Record rate limit event
            await self.record_verification_code_request(contact_id, user_id)

            # Send code via appropriate channel
            try:
                if contact_type == VerificationType.EMAIL:
                    await self.email_service.send_verification_email(contact_value, code)
                else:
                    await self.sms_service.send_verification_sms(contact_value, code)

                logger.info(
                    "verification_code_sent",
                    contact_id=str(contact_id),
                    contact_type=contact_type.value,
                )
            except Exception as e:
                logger.error(
                    "verification_code_send_failed",
                    contact_id=str(contact_id),
                    error=str(e),
                )
                raise HTTPException(
                    status_code=500,
                    detail="Failed to send verification code. Please try again later.",
                ) from e

    async def verify_code(self, code: str, contact_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """
        Verify a code for a contact.

        Args:
            code: 6-digit verification code
            contact_id: UUID of the contact being verified
            user_id: UUID of the user

        Returns:
            True if verification succeeded

        Raises:
            HTTPException: If code is invalid, expired, or already used
        """
        with service_span(
            "verification.verify_code",
            "verification-service",
        ) as span:
            span.set_attribute("verification.contact_id", str(contact_id))
            span.set_attribute("verification.user_id", str(user_id))
            # Find the most recent unused verification code for this user and contact
            result = await self.db.execute(
                select(VerificationCode)
                .where(
                    VerificationCode.user_id == user_id,
                    VerificationCode.contact_id == contact_id,
                    VerificationCode.code == code,
                    VerificationCode.used == False,  # noqa: E712
                )
                .order_by(VerificationCode.created_at.desc())
                .limit(1)
            )
            verification_code = result.scalar_one_or_none()

            if not verification_code:
                logger.warning(
                    "verification_code_not_found",
                    user_id=str(user_id),
                    contact_id=str(contact_id),
                )
                span.set_attribute("verification.result", False)
                raise HTTPException(
                    status_code=400,
                    detail="Invalid verification code.",
                )

            if verification_code.is_expired:
                logger.warning(
                    "verification_code_expired",
                    user_id=str(user_id),
                    contact_id=str(contact_id),
                )
                span.set_attribute("verification.result", False)
                raise HTTPException(
                    status_code=400,
                    detail="Verification code has expired. Please request a new one.",
                )

            # Validate contact exists and belongs to user (hoisted from conditional)
            contact = await get_contact_by_id(contact_id, user_id, self.db)

            # Mark code as used and contact as verified
            verification_code.used = True
            contact.verified = True
            await self.db.commit()

            # Reset rate limit after successful verification
            await self.reset_verification_rate_limit(contact_id)

            logger.info(
                "contact_verified",
                contact_id=str(contact_id),
                user_id=str(user_id),
                contact_type=verification_code.type.value,
            )

            span.set_attribute("verification.result", True)
            return True
