"""Celery Beat periodic task schedules.

This module configures the schedule for periodic tasks that run automatically
via Celery Beat. The check_disruptions_and_alert task runs every 30 seconds
to monitor TfL status and send alerts to users with matching notification preferences.

The detect_and_rebuild_stale_routes task runs daily at 3 AM to ensure route
station indexes stay accurate as TfL line data changes over time.
"""

from app.celery.app import celery_app
from celery.schedules import crontab, schedule

# Configure Celery Beat schedule
celery_app.conf.beat_schedule = {
    "check-disruptions-and-alert": {
        "task": "app.celery.tasks.check_disruptions_and_alert",
        "schedule": schedule(run_every=30.0),  # Run every 30 seconds
        "options": {
            "expires": 60,  # Task expires if not picked up within 60 seconds
        },
    },
    "detect-stale-routes": {
        "task": "app.celery.tasks.detect_and_rebuild_stale_routes",
        "schedule": crontab(hour=3, minute=0),  # Run daily at 3 AM
        "options": {
            "expires": 3600,  # Task expires if not picked up within 1 hour
        },
    },
}
