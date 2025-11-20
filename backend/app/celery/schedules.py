"""Celery Beat periodic task schedules.

This module configures the schedule for periodic tasks that run automatically
via Celery Beat.

Scheduled tasks:
- check_disruptions_and_alert: Every 30 seconds - monitor TfL disruptions and send alerts
- refresh_tfl_metadata: Daily - refresh severity codes, categories, stop types with change detection
- rebuild_network_graph: Daily - rebuild station graph and trigger stale route detection

Note: Route index staleness detection is event-driven (triggered after TfL data updates)
rather than scheduled. See POST /admin/tfl/build-graph endpoint.
"""

from app.celery.app import celery_app
from celery.schedules import schedule

# Schedule configuration constants
DISRUPTION_CHECK_INTERVAL = 30.0  # 30 seconds
METADATA_REFRESH_INTERVAL = 86400.0  # 24 hours (daily)
GRAPH_REBUILD_INTERVAL = 86400.0  # 24 hours (daily)

# Configure Celery Beat schedule
celery_app.conf.beat_schedule = {
    "check-disruptions-and-alert": {
        "task": "app.celery.tasks.check_disruptions_and_alert",
        "schedule": schedule(run_every=DISRUPTION_CHECK_INTERVAL),
        "options": {
            "expires": 60,  # Task expires if not picked up within 60 seconds
        },
    },
    "refresh-tfl-metadata": {
        "task": "app.celery.tasks.refresh_tfl_metadata",
        "schedule": schedule(run_every=METADATA_REFRESH_INTERVAL),
        "options": {
            "expires": 3600,  # Task expires if not picked up within 1 hour
        },
    },
    "rebuild-network-graph": {
        "task": "app.celery.tasks.rebuild_network_graph",
        "schedule": schedule(run_every=GRAPH_REBUILD_INTERVAL),
        "options": {
            "expires": 3600,  # Task expires if not picked up within 1 hour
        },
    },
}
