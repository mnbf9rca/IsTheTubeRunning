"""Celery Beat periodic task schedules.

This module configures the schedule for periodic tasks that run automatically
via Celery Beat. The check_disruptions_and_alert task runs every 30 seconds
to monitor TfL status and send alerts to users with matching notification preferences.

Note: Route index staleness detection is event-driven (triggered after TfL data updates)
rather than scheduled. See POST /admin/tfl/build-graph endpoint.
"""

from app.celery.app import celery_app
from celery.schedules import schedule

# Configure Celery Beat schedule
celery_app.conf.beat_schedule = {
    "check-disruptions-and-alert": {
        "task": "app.celery.tasks.check_disruptions_and_alert",
        "schedule": schedule(run_every=30.0),  # Run every 30 seconds
        "options": {
            "expires": 60,  # Task expires if not picked up within 60 seconds
        },
    },
}
