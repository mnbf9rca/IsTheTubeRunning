"""Pydantic schemas for admin endpoints."""

from datetime import datetime
from uuid import UUID

from app.models.notification import NotificationMethod, NotificationStatus
from pydantic import BaseModel, ConfigDict, Field

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
