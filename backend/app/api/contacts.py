"""Contacts API endpoints for managing email addresses and phone numbers."""

from datetime import datetime
from uuid import UUID

import phonenumbers
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.user import EmailAddress, PhoneNumber, User, VerificationType
from app.services.contact_service import get_contact_by_id
from app.services.verification_service import VerificationService

router = APIRouter(prefix="/contacts", tags=["contacts"])


# ==================== Pydantic Schemas ====================


class AddEmailRequest(BaseModel):
    """Request to add a new email address."""

    email: EmailStr

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        """Normalize email to lowercase for case-insensitive duplicate detection."""
        return v.lower()


class AddPhoneRequest(BaseModel):
    """Request to add a new phone number."""

    phone: str  # E.164 format recommended (e.g., +14155552671)

    @field_validator("phone", mode="after")
    @classmethod
    def normalize_phone(cls, v: str) -> str:
        """
        Validate and normalize phone number to E.164 format.

        This ensures consistent storage and duplicate detection regardless of input formatting.

        Args:
            v: Phone number in any format

        Returns:
            Normalized E.164 format phone number (e.g., +442012345678)

        Raises:
            ValueError: If phone number is invalid
        """
        try:
            # Parse with None region (requires + prefix) or try common defaults
            parsed = phonenumbers.parse(v, None if v.startswith("+") else "US")

            # Validate the number
            if not phonenumbers.is_valid_number(parsed):
                raise ValueError

            # Return in E.164 format
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except phonenumbers.NumberParseException as e:
            error_msg = f"Invalid phone number format: {e}"
            raise ValueError(error_msg) from e


class EmailResponse(BaseModel):
    """Email address response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    verified: bool
    is_primary: bool
    created_at: datetime


class PhoneResponse(BaseModel):
    """Phone number response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    phone: str
    verified: bool
    is_primary: bool
    created_at: datetime


class ContactsResponse(BaseModel):
    """Response containing all user contacts."""

    emails: list[EmailResponse]
    phones: list[PhoneResponse]


class VerifyCodeRequest(BaseModel):
    """Request to verify a code."""

    contact_id: UUID
    code: str


class VerifyCodeResponse(BaseModel):
    """Response after successful verification."""

    success: bool
    message: str


class SendVerificationResponse(BaseModel):
    """Response after sending verification code."""

    success: bool
    message: str


# ==================== API Endpoints ====================


@router.post("/email", response_model=EmailResponse, status_code=status.HTTP_201_CREATED)
async def add_email(
    request: AddEmailRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EmailAddress:
    """
    Add a new email address to the user's account.

    The email will be added as unverified. Use the send-verification
    endpoint to send a verification code.

    Args:
        request: Email address to add
        current_user: Authenticated user
        db: Database session

    Returns:
        Created email address

    Raises:
        HTTPException: 409 if email already exists, 429 if rate limit exceeded
    """
    verification_service = VerificationService(db)

    # Store user_id before any potential rollback
    user_id = current_user.id

    # Check rate limit for failed additions
    await verification_service.check_add_contact_rate_limit(user_id)

    # Determine if this should be primary (first email)
    result = await db.execute(select(EmailAddress).where(EmailAddress.user_id == user_id))
    existing_emails = result.scalars().all()
    is_first = len(existing_emails) == 0

    # Create email address
    email = EmailAddress(
        user_id=user_id,
        email=request.email,
        verified=False,
        is_primary=is_first,
    )

    try:
        db.add(email)
        await db.commit()
        await db.refresh(email)
        return email
    except IntegrityError:
        await db.rollback()
        # Record failed attempt for rate limiting
        await verification_service.record_add_contact_failure(user_id, request.email)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email address is already registered.",
        ) from None


@router.post("/phone", response_model=PhoneResponse, status_code=status.HTTP_201_CREATED)
async def add_phone(
    request: AddPhoneRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PhoneNumber:
    """
    Add a new phone number to the user's account.

    The phone will be added as unverified. Use the send-verification
    endpoint to send a verification code.

    Args:
        request: Phone number to add (E.164 format recommended)
        current_user: Authenticated user
        db: Database session

    Returns:
        Created phone number

    Raises:
        HTTPException: 409 if phone already exists, 429 if rate limit exceeded
    """
    verification_service = VerificationService(db)

    # Store user_id before any potential rollback
    user_id = current_user.id

    # Check rate limit for failed additions
    await verification_service.check_add_contact_rate_limit(user_id)

    # Determine if this should be primary (first phone)
    result = await db.execute(select(PhoneNumber).where(PhoneNumber.user_id == user_id))
    existing_phones = result.scalars().all()
    is_first = len(existing_phones) == 0

    # Create phone number
    phone = PhoneNumber(
        user_id=user_id,
        phone=request.phone,
        verified=False,
        is_primary=is_first,
    )

    try:
        db.add(phone)
        await db.commit()
        await db.refresh(phone)
        return phone
    except IntegrityError:
        await db.rollback()
        # Record failed attempt for rate limiting
        await verification_service.record_add_contact_failure(user_id, request.phone)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This phone number is already registered.",
        ) from None


@router.post("/{contact_id}/send-verification", response_model=SendVerificationResponse)
async def send_verification(
    contact_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SendVerificationResponse:
    """
    Send a verification code to an email or phone.

    Rate limited to 3 requests per hour per contact.

    Args:
        contact_id: UUID of the email or phone to verify
        current_user: Authenticated user
        db: Database session

    Returns:
        Success response

    Raises:
        HTTPException: 404 if contact not found, 429 if rate limit exceeded
    """
    verification_service = VerificationService(db)

    # Find and validate contact ownership using helper function
    contact = await get_contact_by_id(contact_id, current_user.id, db)

    # Determine contact type and value
    if isinstance(contact, EmailAddress):
        contact_type = VerificationType.EMAIL
        contact_value = contact.email
        message = "Verification code sent to your email address."
    else:  # PhoneNumber
        contact_type = VerificationType.SMS
        contact_value = contact.phone
        message = "Verification code sent to your phone number."

    await verification_service.create_and_send_code(
        contact_id=contact_id,
        user_id=current_user.id,
        contact_type=contact_type,
        contact_value=contact_value,
    )

    return SendVerificationResponse(
        success=True,
        message=message,
    )


@router.post("/verify", response_model=VerifyCodeResponse)
async def verify_code(
    request: VerifyCodeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VerifyCodeResponse:
    """
    Verify a contact using a verification code.

    Args:
        request: Verification code and contact ID
        current_user: Authenticated user
        db: Database session

    Returns:
        Success response

    Raises:
        HTTPException: 400 if code is invalid/expired, 404 if contact not found
    """
    verification_service = VerificationService(db)

    await verification_service.verify_code(
        code=request.code,
        contact_id=request.contact_id,
        user_id=current_user.id,
    )

    return VerifyCodeResponse(
        success=True,
        message="Contact verified successfully.",
    )


@router.get("", response_model=ContactsResponse)
async def list_contacts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ContactsResponse:
    """
    List all contacts (emails and phones) for the current user.

    Args:
        current_user: Authenticated user
        db: Database session

    Returns:
        All user contacts with verification status
    """
    # Get all emails
    result = await db.execute(
        select(EmailAddress)
        .where(EmailAddress.user_id == current_user.id)
        .order_by(EmailAddress.is_primary.desc(), EmailAddress.created_at)
    )
    emails = result.scalars().all()

    # Get all phones
    result = await db.execute(
        select(PhoneNumber)
        .where(PhoneNumber.user_id == current_user.id)
        .order_by(PhoneNumber.is_primary.desc(), PhoneNumber.created_at)
    )
    phones = result.scalars().all()

    return ContactsResponse(
        emails=[EmailResponse.model_validate(e) for e in emails],
        phones=[PhoneResponse.model_validate(p) for p in phones],
    )


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(
    contact_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete an email or phone contact.

    Args:
        contact_id: UUID of the contact to delete
        current_user: Authenticated user
        db: Database session

    Raises:
        HTTPException: 404 if contact not found or doesn't belong to user
    """
    # Find and validate contact ownership using helper function
    contact = await get_contact_by_id(contact_id, current_user.id, db)

    # Delete the contact
    await db.delete(contact)
    await db.commit()


@router.patch("/{contact_id}/primary", response_model=EmailResponse | PhoneResponse)
async def set_primary_contact(
    contact_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EmailAddress | PhoneNumber:
    """
    Set a contact as the primary contact.

    Only verified contacts can be set as primary.
    Only one email and one phone can be primary at a time.

    Args:
        contact_id: UUID of the contact to set as primary
        current_user: Authenticated user
        db: Database session

    Returns:
        Updated contact

    Raises:
        HTTPException: 404 if contact not found or doesn't belong to user,
                      400 if contact is not verified
    """
    # Find and validate contact ownership using helper function
    contact = await get_contact_by_id(contact_id, current_user.id, db)

    # Validate contact is verified
    if not contact.verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only verified contacts can be set as primary.",
        )

    # Unset any other primary contact of the same type
    if isinstance(contact, EmailAddress):
        if (
            current_primary_email := (
                await db.execute(
                    select(EmailAddress).where(
                        EmailAddress.user_id == current_user.id,
                        EmailAddress.is_primary == True,  # noqa: E712
                    )
                )
            ).scalar_one_or_none()
        ) and current_primary_email.id != contact_id:
            current_primary_email.is_primary = False
    elif (
        current_primary_phone := (
            await db.execute(
                select(PhoneNumber).where(
                    PhoneNumber.user_id == current_user.id,
                    PhoneNumber.is_primary == True,  # noqa: E712
                )
            )
        ).scalar_one_or_none()
    ) and current_primary_phone.id != contact_id:
        current_primary_phone.is_primary = False

    # Set this contact as primary
    contact.is_primary = True
    await db.commit()
    await db.refresh(contact)
    return contact
