"""Database models for IsTheTubeRunning application."""

# Import Base first
# Import all models to register them with SQLAlchemy metadata
from app.models.admin import AdminRole, AdminUser
from app.models.base import Base, BaseModel
from app.models.notification import (
    NotificationLog,
    NotificationMethod,
    NotificationPreference,
    NotificationStatus,
)
from app.models.rate_limit import RateLimitAction, RateLimitLog
from app.models.route import Route, RouteSchedule, RouteSegment
from app.models.route_index import RouteStationIndex
from app.models.tfl import Line, Station, StationConnection
from app.models.user import (
    EmailAddress,
    PhoneNumber,
    User,
    VerificationCode,
    VerificationType,
)

__all__ = [
    # Base
    "Base",
    "BaseModel",
    # User models
    "User",
    "EmailAddress",
    "PhoneNumber",
    "VerificationCode",
    "VerificationType",
    # Rate limiting models
    "RateLimitLog",
    "RateLimitAction",
    # TfL models
    "Line",
    "Station",
    "StationConnection",
    # Route models
    "Route",
    "RouteSegment",
    "RouteSchedule",
    "RouteStationIndex",
    # Notification models
    "NotificationPreference",
    "NotificationLog",
    "NotificationMethod",
    "NotificationStatus",
    # Admin models
    "AdminUser",
    "AdminRole",
]
