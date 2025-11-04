"""Celery task queue for background processing."""

from app.celery.app import celery_app

__all__ = ["celery_app"]
