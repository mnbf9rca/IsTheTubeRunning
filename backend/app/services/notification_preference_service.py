"""Notification preference management service."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.notification import NotificationMethod, NotificationPreference
from app.models.route import Route
from app.models.user import EmailAddress, PhoneNumber


class NotificationPreferenceService:
    """Service for managing notification preferences."""

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize the notification preference service.

        Args:
            db: Database session
        """
        self.db = db

    async def get_preference_by_id(
        self,
        preference_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> NotificationPreference:
        """
        Get a notification preference by ID with ownership validation.

        Args:
            preference_id: Preference UUID
            user_id: User UUID (for ownership check via route)

        Returns:
            NotificationPreference object

        Raises:
            HTTPException: 404 if preference not found or user doesn't own the route
        """
        # Join with route to validate ownership
        query = (
            select(NotificationPreference)
            .join(Route, NotificationPreference.route_id == Route.id)
            .where(
                NotificationPreference.id == preference_id,
                Route.user_id == user_id,
            )
        )

        result = await self.db.execute(query)

        if not (preference := result.scalar_one_or_none()):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification preference not found.",
            )

        return preference

    async def list_preferences(
        self,
        route_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> list[NotificationPreference]:
        """
        List all notification preferences for a route.

        Args:
            route_id: Route UUID
            user_id: User UUID (for ownership check)

        Returns:
            List of notification preferences

        Raises:
            HTTPException: 404 if route not found or doesn't belong to user
        """
        # First validate route ownership
        route_result = await self.db.execute(
            select(Route).where(
                Route.id == route_id,
                Route.user_id == user_id,
            )
        )

        if not route_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Route not found.",
            )

        # Get preferences
        result = await self.db.execute(
            select(NotificationPreference)
            .where(NotificationPreference.route_id == route_id)
            .order_by(NotificationPreference.created_at.desc())
        )

        return list(result.scalars().all())

    async def create_preference(  # noqa: PLR0912
        self,
        route_id: uuid.UUID,
        user_id: uuid.UUID,
        method: NotificationMethod,
        target_email_id: uuid.UUID | None,
        target_phone_id: uuid.UUID | None,
    ) -> NotificationPreference:
        """
        Create a new notification preference.

        Args:
            route_id: Route UUID
            user_id: User UUID (for ownership validation)
            method: Notification method (email or sms)
            target_email_id: Email address ID (required if method is email)
            target_phone_id: Phone number ID (required if method is sms)

        Returns:
            Created notification preference

        Raises:
            HTTPException: Various validation errors (400, 404, 409)
        """
        # Validate route ownership
        route_result = await self.db.execute(
            select(Route).where(
                Route.id == route_id,
                Route.user_id == user_id,
            )
        )

        if not route_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Route not found.",
            )

        # Validate exactly one target is provided
        if (target_email_id is None and target_phone_id is None) or (
            target_email_id is not None and target_phone_id is not None
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Exactly one of target_email_id or target_phone_id must be provided.",
            )

        # Validate method matches target type
        if method == NotificationMethod.EMAIL and target_email_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email method requires target_email_id.",
            )

        if method == NotificationMethod.SMS and target_phone_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SMS method requires target_phone_id.",
            )

        # Validate contact ownership and verification
        if target_email_id is not None:
            email_result = await self.db.execute(
                select(EmailAddress).where(
                    EmailAddress.id == target_email_id,
                    EmailAddress.user_id == user_id,
                )
            )

            if not (email := email_result.scalar_one_or_none()):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Email address not found.",
                )

            if not email.verified:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email address must be verified.",
                )

        if target_phone_id is not None:
            phone_result = await self.db.execute(
                select(PhoneNumber).where(
                    PhoneNumber.id == target_phone_id,
                    PhoneNumber.user_id == user_id,
                )
            )

            if not (phone := phone_result.scalar_one_or_none()):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Phone number not found.",
                )

            if not phone.verified:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Phone number must be verified.",
                )

        # Check for duplicates (same route + contact + method)
        duplicate_query = select(NotificationPreference).where(
            NotificationPreference.route_id == route_id,
            NotificationPreference.method == method,
        )

        if target_email_id is not None:
            duplicate_query = duplicate_query.where(NotificationPreference.target_email_id == target_email_id)
        if target_phone_id is not None:
            duplicate_query = duplicate_query.where(NotificationPreference.target_phone_id == target_phone_id)

        duplicate_result = await self.db.execute(duplicate_query)

        if duplicate_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Notification preference already exists for this route and contact.",
            )

        # Check preference count limit
        count_result = await self.db.execute(
            select(func.count()).select_from(NotificationPreference).where(NotificationPreference.route_id == route_id)
        )

        count = count_result.scalar_one()

        if count >= settings.MAX_NOTIFICATION_PREFERENCES_PER_ROUTE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Maximum {settings.MAX_NOTIFICATION_PREFERENCES_PER_ROUTE} notification preferences per route.",
            )

        # Create preference
        preference = NotificationPreference(
            route_id=route_id,
            method=method,
            target_email_id=target_email_id,
            target_phone_id=target_phone_id,
        )

        self.db.add(preference)
        await self.db.commit()
        await self.db.refresh(preference)

        return preference

    async def update_preference(  # noqa: PLR0912, PLR0915
        self,
        preference_id: uuid.UUID,
        user_id: uuid.UUID,
        method: NotificationMethod | None,
        target_email_id: uuid.UUID | None,
        target_phone_id: uuid.UUID | None,
    ) -> NotificationPreference:
        """
        Update a notification preference.

        Args:
            preference_id: Preference UUID
            user_id: User UUID (for ownership validation)
            method: New notification method (optional)
            target_email_id: New email address ID (optional)
            target_phone_id: New phone number ID (optional)

        Returns:
            Updated notification preference

        Raises:
            HTTPException: Various validation errors (400, 404, 409)
        """
        # Get existing preference with ownership check
        preference = await self.get_preference_by_id(preference_id, user_id)

        # Load route for later validation
        await self.db.refresh(preference, attribute_names=["route"])
        route_id = preference.route_id

        # If both targets provided in update, reject
        if target_email_id is not None and target_phone_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot specify both target_email_id and target_phone_id.",
            )

        # Determine final values
        final_method = method if method is not None else preference.method

        # If switching targets, clear the other one
        if target_email_id is not None:
            # Explicitly setting email, clear phone
            final_email_id = target_email_id
            final_phone_id = None
        elif target_phone_id is not None:
            # Explicitly setting phone, clear email
            final_phone_id = target_phone_id
            final_email_id = None
        else:
            # No target change, keep existing
            final_email_id = preference.target_email_id
            final_phone_id = preference.target_phone_id

        # Validate exactly one target is set
        if (final_email_id is None and final_phone_id is None) or (
            final_email_id is not None and final_phone_id is not None
        ):
            # This defensive line would only execute if the database constraint was somehow
            # bypassed, which shouldn't happen...
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Exactly one of target_email_id or target_phone_id must be set.",
            )

        # Validate method matches target type
        if final_method == NotificationMethod.EMAIL and final_email_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email method requires target_email_id.",
            )

        if final_method == NotificationMethod.SMS and final_phone_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SMS method requires target_phone_id.",
            )

        # Validate new contact ownership and verification (if changed)
        if target_email_id is not None and target_email_id != preference.target_email_id:
            email_result = await self.db.execute(
                select(EmailAddress).where(
                    EmailAddress.id == target_email_id,
                    EmailAddress.user_id == user_id,
                )
            )

            if not (email := email_result.scalar_one_or_none()):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Email address not found.",
                )

            if not email.verified:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email address must be verified.",
                )

        if target_phone_id is not None and target_phone_id != preference.target_phone_id:
            phone_result = await self.db.execute(
                select(PhoneNumber).where(
                    PhoneNumber.id == target_phone_id,
                    PhoneNumber.user_id == user_id,
                )
            )

            if not (phone := phone_result.scalar_one_or_none()):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Phone number not found.",
                )

            if not phone.verified:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Phone number must be verified.",
                )

        # Check for duplicates (excluding current preference)
        duplicate_query = select(NotificationPreference).where(
            NotificationPreference.route_id == route_id,
            NotificationPreference.method == final_method,
            NotificationPreference.id != preference_id,
        )

        if final_email_id is not None:
            duplicate_query = duplicate_query.where(NotificationPreference.target_email_id == final_email_id)
        if final_phone_id is not None:
            duplicate_query = duplicate_query.where(NotificationPreference.target_phone_id == final_phone_id)

        duplicate_result = await self.db.execute(duplicate_query)

        if duplicate_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Notification preference already exists for this route and contact.",
            )

        # Update fields
        if method is not None:
            preference.method = method
        if target_email_id is not None:
            preference.target_email_id = target_email_id
            preference.target_phone_id = None  # Clear the other target
        if target_phone_id is not None:
            preference.target_phone_id = target_phone_id
            preference.target_email_id = None  # Clear the other target

        await self.db.commit()
        await self.db.refresh(preference)

        return preference

    async def delete_preference(
        self,
        preference_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """
        Delete a notification preference.

        Args:
            preference_id: Preference UUID
            user_id: User UUID (for ownership validation)

        Raises:
            HTTPException: 404 if preference not found
        """
        # Validate ownership
        preference = await self.get_preference_by_id(preference_id, user_id)

        await self.db.delete(preference)
        await self.db.commit()
