"""Notification preferences API endpoints."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.notification import NotificationMethod, NotificationPreference
from app.models.user import User
from app.services.notification_preference_service import NotificationPreferenceService

router = APIRouter(tags=["notification-preferences"])


# ==================== Pydantic Schemas ====================


class CreateNotificationPreferenceRequest(BaseModel):
    """Request to create a new notification preference."""

    method: NotificationMethod
    target_email_id: UUID | None = None
    target_phone_id: UUID | None = None

    @model_validator(mode="after")
    def validate_exactly_one_target(self) -> "CreateNotificationPreferenceRequest":
        """Validate that exactly one target is provided."""
        email_id = self.target_email_id
        phone_id = self.target_phone_id

        if (email_id is None and phone_id is None) or (email_id is not None and phone_id is not None):
            msg = "Exactly one of target_email_id or target_phone_id must be provided."
            raise ValueError(msg)

        return self


class UpdateNotificationPreferenceRequest(BaseModel):
    """Request to update a notification preference."""

    method: NotificationMethod | None = None
    target_email_id: UUID | None = None
    target_phone_id: UUID | None = None

    @model_validator(mode="after")
    def validate_not_both_targets(self) -> "UpdateNotificationPreferenceRequest":
        """Validate that both targets are not provided simultaneously."""
        if self.target_email_id is not None and self.target_phone_id is not None:
            msg = "Cannot specify both target_email_id and target_phone_id."
            raise ValueError(msg)

        return self


class NotificationPreferenceResponse(BaseModel):
    """Notification preference response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    route_id: UUID
    method: NotificationMethod
    target_email_id: UUID | None
    target_phone_id: UUID | None
    created_at: datetime
    updated_at: datetime


# ==================== API Endpoints ====================


@router.get(
    "/routes/{route_id}/notifications",
    response_model=list[NotificationPreferenceResponse],
)
async def list_notification_preferences(
    route_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[NotificationPreference]:
    """
    List all notification preferences for a route.

    Args:
        route_id: Route UUID
        current_user: Authenticated user
        db: Database session

    Returns:
        List of notification preferences

    Raises:
        HTTPException: 404 if route not found or doesn't belong to user
    """
    service = NotificationPreferenceService(db)
    return await service.list_preferences(route_id, current_user.id)


@router.post(
    "/routes/{route_id}/notifications",
    response_model=NotificationPreferenceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_notification_preference(
    route_id: UUID,
    request: CreateNotificationPreferenceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationPreference:
    """
    Create a new notification preference for a route.

    Args:
        route_id: Route UUID
        request: Notification preference creation request
        current_user: Authenticated user
        db: Database session

    Returns:
        Created notification preference

    Raises:
        HTTPException: 400 (validation errors), 404 (route/contact not found),
                      409 (duplicate), 429 (rate limit)
    """
    service = NotificationPreferenceService(db)
    return await service.create_preference(
        route_id=route_id,
        user_id=current_user.id,
        method=request.method,
        target_email_id=request.target_email_id,
        target_phone_id=request.target_phone_id,
    )


@router.patch(
    "/routes/{route_id}/notifications/{preference_id}",
    response_model=NotificationPreferenceResponse,
)
async def update_notification_preference(
    route_id: UUID,
    preference_id: UUID,
    request: UpdateNotificationPreferenceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationPreference:
    """
    Update a notification preference.

    Args:
        route_id: Route UUID (validated against preference's route)
        preference_id: Preference UUID
        request: Update request
        current_user: Authenticated user
        db: Database session

    Returns:
        Updated notification preference

    Raises:
        HTTPException: 400 (validation errors, route mismatch), 404 (preference/contact not found),
                      409 (duplicate)
    """
    service = NotificationPreferenceService(db)

    # Validate route_id matches the preference's route
    preference = await service.get_preference_by_id(preference_id, current_user.id)
    if preference.route_id != route_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Route ID in URL does not match preference's route.",
        )

    return await service.update_preference(
        preference_id=preference_id,
        user_id=current_user.id,
        method=request.method,
        target_email_id=request.target_email_id,
        target_phone_id=request.target_phone_id,
    )


@router.delete(
    "/routes/{route_id}/notifications/{preference_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_notification_preference(
    route_id: UUID,
    preference_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a notification preference.

    Args:
        route_id: Route UUID (validated against preference's route)
        preference_id: Preference UUID
        current_user: Authenticated user
        db: Database session

    Raises:
        HTTPException: 400 (route mismatch), 404 (preference not found or doesn't belong to user)
    """
    service = NotificationPreferenceService(db)

    # Validate route_id matches the preference's route
    preference = await service.get_preference_by_id(preference_id, current_user.id)
    if preference.route_id != route_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Route ID in URL does not match preference's route.",
        )

    await service.delete_preference(preference_id, current_user.id)
