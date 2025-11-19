"""Middleware for the application."""

from app.middleware.access_logging import AccessLoggingMiddleware

__all__ = ["AccessLoggingMiddleware"]
