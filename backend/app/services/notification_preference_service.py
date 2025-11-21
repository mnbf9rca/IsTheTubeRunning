"""Notification preference management service."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.helpers.soft_delete_filters import add_active_filter, add_active_filters, soft_delete
from app.models.notification import NotificationMethod, NotificationPreference
from app.models.user import EmailAddress, PhoneNumber
from app.models.user_route import UserRoute


class NotificationPreferenceService:
    """Service for managing notification preferences."""

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize the notification preference service.

        Args:
            db: Database session
        """
        self.db = db

    # ==================== Private Helper Methods ====================

    async def _validate_email_ownership_and_verification(
        self,
        email_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> EmailAddress:
        """
        Validate email ownership and verification status.

        Args:
            email_id: Email address ID
            user_id: User ID for ownership check

        Returns:
            EmailAddress object

        Raises:
            HTTPException: 404 if not found, 400 if not verified
        """
        result = await self.db.execute(
            select(EmailAddress).where(
                EmailAddress.id == email_id,
                EmailAddress.user_id == user_id,
            )
        )

        if not (email := result.scalar_one_or_none()):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Email address not found.",
            )

        if not email.verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address must be verified.",
            )

        return email

    async def _validate_phone_ownership_and_verification(
        self,
        phone_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> PhoneNumber:
        """
        Validate phone ownership and verification status.

        Args:
            phone_id: Phone number ID
            user_id: User ID for ownership check

        Returns:
            PhoneNumber object

        Raises:
            HTTPException: 404 if not found, 400 if not verified
        """
        result = await self.db.execute(
            select(PhoneNumber).where(
                PhoneNumber.id == phone_id,
                PhoneNumber.user_id == user_id,
            )
        )

        if not (phone := result.scalar_one_or_none()):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Phone number not found.",
            )

        if not phone.verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number must be verified.",
            )

        return phone

    async def _check_duplicate_preference(
        self,
        route_id: uuid.UUID,
        method: NotificationMethod,
        email_id: uuid.UUID | None,
        phone_id: uuid.UUID | None,
        exclude_preference_id: uuid.UUID | None = None,
    ) -> None:
        """
        Check for duplicate preferences.

        Args:
            route_id: UserRoute UUID
            method: Notification method
            email_id: Email address ID (if email method)
            phone_id: Phone number ID (if SMS method)
            exclude_preference_id: Preference ID to exclude from check (for updates)

        Raises:
            HTTPException: 409 if duplicate exists
        """
        query = select(NotificationPreference).where(
            NotificationPreference.route_id == route_id,
            NotificationPreference.method == method,
        )
        # Only check active (non-deleted) preferences (Issue #233)
        query = add_active_filter(query, NotificationPreference)

        if exclude_preference_id is not None:
            query = query.where(NotificationPreference.id != exclude_preference_id)

        if email_id is not None:
            query = query.where(NotificationPreference.target_email_id == email_id)
        if phone_id is not None:
            query = query.where(NotificationPreference.target_phone_id == phone_id)

        result = await self.db.execute(query)

        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Notification preference already exists for this route and contact.",
            )

    # ==================== Public API Methods ====================

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
            .join(UserRoute, NotificationPreference.route_id == UserRoute.id)
            .where(
                NotificationPreference.id == preference_id,
                UserRoute.user_id == user_id,
            )
        )
        # Only retrieve active (non-deleted) preferences and routes (Issue #233)
        query = add_active_filters(query, NotificationPreference, UserRoute)

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
            route_id: UserRoute UUID
            user_id: User UUID (for ownership check)

        Returns:
            List of notification preferences

        Raises:
            HTTPException: 404 if route not found or doesn't belong to user
        """
        # First validate route ownership
        route_result = await self.db.execute(
            select(UserRoute).where(
                UserRoute.id == route_id,
                UserRoute.user_id == user_id,
                UserRoute.deleted_at.is_(None),
            )
        )

        if not route_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="UserRoute not found.",
            )

        # Get preferences (only active/non-deleted) (Issue #233)
        query = select(NotificationPreference).where(NotificationPreference.route_id == route_id)
        query = add_active_filter(query, NotificationPreference)
        query = query.order_by(NotificationPreference.created_at.desc())

        result = await self.db.execute(query)

        return list(result.scalars().all())

    async def create_preference(
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
            route_id: UserRoute UUID
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
            select(UserRoute).where(
                UserRoute.id == route_id,
                UserRoute.user_id == user_id,
                UserRoute.deleted_at.is_(None),
            )
        )

        if not route_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="UserRoute not found.",
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

        # Validate contact ownership and verification using helper methods
        if target_email_id is not None:
            await self._validate_email_ownership_and_verification(target_email_id, user_id)

        if target_phone_id is not None:
            await self._validate_phone_ownership_and_verification(target_phone_id, user_id)

        # Check for duplicates using helper method
        await self._check_duplicate_preference(
            route_id=route_id,
            method=method,
            email_id=target_email_id,
            phone_id=target_phone_id,
        )

        # Check preference count limit (only active/non-deleted) (Issue #233)
        count_query = (
            select(func.count()).select_from(NotificationPreference).where(NotificationPreference.route_id == route_id)
        )
        count_query = add_active_filter(count_query, NotificationPreference)
        count_result = await self.db.execute(count_query)

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

    async def update_preference(
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
            final_email_id = target_email_id
            final_phone_id = None
        elif target_phone_id is not None:
            final_phone_id = target_phone_id
            final_email_id = None
        else:
            final_email_id = preference.target_email_id
            final_phone_id = preference.target_phone_id

        # Validate exactly one target is set (defensive check)
        if (final_email_id is None and final_phone_id is None) or (
            final_email_id is not None and final_phone_id is not None
        ):
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

        # Validate new contact ownership and verification (if changed) using helper methods
        if target_email_id is not None and target_email_id != preference.target_email_id:
            await self._validate_email_ownership_and_verification(target_email_id, user_id)

        if target_phone_id is not None and target_phone_id != preference.target_phone_id:
            await self._validate_phone_ownership_and_verification(target_phone_id, user_id)

        # Check for duplicates using helper method
        await self._check_duplicate_preference(
            route_id=route_id,
            method=final_method,
            email_id=final_email_id,
            phone_id=final_phone_id,
            exclude_preference_id=preference_id,
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
        # Validate ownership (will raise 404 if not found or not owned by user)
        await self.get_preference_by_id(preference_id, user_id)

        # Soft delete the notification preference (Issue #233)
        await soft_delete(self.db, NotificationPreference, NotificationPreference.id == preference_id)
        await self.db.commit()
