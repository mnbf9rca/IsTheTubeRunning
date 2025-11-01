"""Health check schemas."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response."""

    status: str


class ReadinessResponse(BaseModel):
    """Readiness check response."""

    status: str


class RootResponse(BaseModel):
    """Root endpoint response."""

    message: str
    version: str
