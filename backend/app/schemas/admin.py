"""Pydantic schemas for admin endpoints."""

from datetime import datetime
from uuid import UUID

from app.models.notification import NotificationMethod, NotificationStatus
from pydantic import BaseModel, ConfigDict, Field

# ==================== Route Index Management Schemas ====================


class RebuildIndexesResponse(BaseModel):
    """Response from rebuilding route station indexes."""

    success: bool = Field(..., description="Whether the rebuild completed successfully")
    rebuilt_count: int = Field(..., description="Number of routes rebuilt")
    failed_count: int = Field(..., description="Number of routes that failed to rebuild")
    errors: list[str] = Field(default_factory=list, description="Error messages for failed routes")


# ==================== Alert Management Schemas ====================


class TriggerCheckResponse(BaseModel):
    """Response from manually triggering an alert check."""

    success: bool = Field(..., description="Whether the check completed successfully")
    message: str = Field(..., description="Human-readable result message")
    routes_checked: int = Field(..., description="Number of routes processed")
    alerts_sent: int = Field(..., description="Number of alerts sent")
    errors: int = Field(..., description="Number of errors encountered")


class WorkerStatusResponse(BaseModel):
    """Response from checking Celery worker status."""

    worker_available: bool = Field(..., description="Whether a worker is available")
    active_tasks: int = Field(..., description="Number of currently executing tasks")
    scheduled_tasks: int = Field(..., description="Number of scheduled tasks")
    last_heartbeat: datetime | None = Field(
        None,
        description="Timestamp of last worker heartbeat (if available)",
    )
    message: str = Field(..., description="Human-readable status message")


# ==================== Notification Log Schemas ====================


class NotificationLogItem(BaseModel):
    """Individual notification log entry."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    route_id: UUID
    sent_at: datetime
    method: NotificationMethod
    status: NotificationStatus
    error_message: str | None = None


class RecentLogsResponse(BaseModel):
    """Response from querying recent notification logs."""

    total: int = Field(..., description="Total number of logs matching filter")
    logs: list[NotificationLogItem] = Field(..., description="List of notification logs")
    limit: int = Field(..., description="Number of logs per page")
    offset: int = Field(..., description="Starting offset for pagination")


# ==================== User Management Schemas ====================


class EmailAddressItem(BaseModel):
    """Email address information."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    verified: bool
    is_primary: bool


class PhoneNumberItem(BaseModel):
    """Phone number information."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    phone: str
    verified: bool
    is_primary: bool


class UserListItem(BaseModel):
    """User item in list view."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    external_id: str
    auth_provider: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    email_addresses: list[EmailAddressItem] = Field(default_factory=list)
    phone_numbers: list[PhoneNumberItem] = Field(default_factory=list)


class PaginatedUsersResponse(BaseModel):
    """Response from paginated user listing."""

    total: int = Field(..., description="Total number of users matching filter")
    users: list[UserListItem] = Field(..., description="List of users")
    limit: int = Field(..., description="Number of users per page")
    offset: int = Field(..., description="Starting offset for pagination")


class RouteBasicInfo(BaseModel):
    """Basic route information for user details."""

    id: UUID
    name: str
    active: bool
    description: str | None = None
    created_at: datetime


class UserDetailResponse(BaseModel):
    """Detailed user information."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    external_id: str
    auth_provider: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    email_addresses: list[EmailAddressItem] = Field(default_factory=list)
    phone_numbers: list[PhoneNumberItem] = Field(default_factory=list)


class AnonymiseUserResponse(BaseModel):
    """Response from user anonymisation."""

    success: bool = Field(..., description="Whether anonymisation succeeded")
    message: str = Field(..., description="Human-readable result message")
    user_id: UUID = Field(..., description="ID of anonymised user")


# ==================== Analytics Schemas ====================


class UserCountMetrics(BaseModel):
    """User count metrics."""

    total_users: int = Field(..., description="Total non-deleted users")
    active_users: int = Field(..., description="Users with active routes")
    users_with_verified_email: int = Field(..., description="Users with verified email")
    users_with_verified_phone: int = Field(..., description="Users with verified phone")
    admin_users: int = Field(..., description="Number of admin users")


class RouteStatMetrics(BaseModel):
    """Route statistics metrics."""

    total_routes: int = Field(..., description="Total non-deleted routes")
    active_routes: int = Field(..., description="Active routes")
    avg_routes_per_user: float = Field(..., description="Average routes per user")


class NotificationStatMetrics(BaseModel):
    """Notification statistics metrics."""

    total_sent: int = Field(..., description="Total notifications sent")
    successful: int = Field(..., description="Successfully sent notifications")
    failed: int = Field(..., description="Failed notifications")
    success_rate: float = Field(..., description="Success rate percentage")
    by_method_last_30_days: dict[str, int] = Field(..., description="Notification counts by method (last 30 days)")


class DailySignup(BaseModel):
    """Daily signup count."""

    date: str = Field(..., description="Date in ISO format")
    count: int = Field(..., description="Number of signups on that day")


class GrowthMetrics(BaseModel):
    """User growth and retention metrics."""

    new_users_last_7_days: int = Field(..., description="New users in last 7 days")
    new_users_last_30_days: int = Field(..., description="New users in last 30 days")
    daily_signups_last_7_days: list[DailySignup] = Field(..., description="Daily signup counts for last 7 days")


class EngagementMetrics(BaseModel):
    """Comprehensive engagement metrics for admin dashboard."""

    user_counts: UserCountMetrics
    route_stats: RouteStatMetrics
    notification_stats: NotificationStatMetrics
    growth_metrics: GrowthMetrics
