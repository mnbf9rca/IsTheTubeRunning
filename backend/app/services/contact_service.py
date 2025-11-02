"""Contact lookup service."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import EmailAddress, PhoneNumber


async def get_contact_by_id(
    contact_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> EmailAddress | PhoneNumber:
    """
    Look up a contact (email or phone) by ID for a specific user.

    This helper eliminates duplicated lookup logic across API endpoints.

    Args:
        contact_id: UUID of the contact to find
        user_id: UUID of the user who owns the contact
        db: Database session

    Returns:
        The EmailAddress or PhoneNumber object

    Raises:
        HTTPException: 404 if contact not found or doesn't belong to user
    """
    # Try to find email first
    if email := (
        await db.execute(
            select(EmailAddress).where(
                EmailAddress.id == contact_id,
                EmailAddress.user_id == user_id,
            )
        )
    ).scalar_one_or_none():
        return email

    # Try to find phone
    if phone := (
        await db.execute(
            select(PhoneNumber).where(
                PhoneNumber.id == contact_id,
                PhoneNumber.user_id == user_id,
            )
        )
    ).scalar_one_or_none():
        return phone

    # Contact not found
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Contact not found.",
    )
