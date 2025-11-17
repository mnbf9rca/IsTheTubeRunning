"""Tests for Celery Beat schedule configuration.

Regression tests to ensure schedules module remains imported and configured.
These tests prevent Issue #167 from recurring.
"""

from app.celery import schedules
from app.celery.app import celery_app

from celery.schedules import schedule


class TestCelerySchedulesImport:
    """Test that schedules module is properly imported and configured."""

    def test_schedules_module_is_imported(self):
        """Test that schedules module exists in app.celery namespace.

        Regression test for Issue #167: schedules.py was not imported,
        causing beat_schedule to remain empty.
        """
        # Verify schedules module can be imported
        assert schedules is not None
        assert hasattr(schedules, "celery_app")

    def test_beat_schedule_is_populated(self):
        """Test that beat_schedule configuration is not empty.

        If schedules.py is not imported, beat_schedule will be an empty dict.
        This test catches that regression.
        """
        assert celery_app.conf.beat_schedule is not None
        assert isinstance(celery_app.conf.beat_schedule, dict)
        assert len(celery_app.conf.beat_schedule) > 0, "beat_schedule is empty - schedules module may not be imported"

    def test_check_disruptions_and_alert_task_exists(self):
        """Test that the check-disruptions-and-alert task is registered.

        This is the primary periodic task that drives the notification system.
        """
        assert "check-disruptions-and-alert" in celery_app.conf.beat_schedule
        task_config = celery_app.conf.beat_schedule["check-disruptions-and-alert"]

        # Verify it's a dict with expected structure
        assert isinstance(task_config, dict)
        assert "task" in task_config
        assert "schedule" in task_config
        assert "options" in task_config


class TestScheduleConfiguration:
    """Test the configuration details of scheduled tasks."""

    def test_check_disruptions_schedule_interval(self):
        """Test that check-disruptions task runs every 30 seconds."""
        task_config = celery_app.conf.beat_schedule["check-disruptions-and-alert"]

        # Verify schedule is a celery.schedules.schedule object
        assert isinstance(task_config["schedule"], schedule)

        # Verify interval is 30 seconds
        # schedule.run_every is a timedelta object
        assert task_config["schedule"].run_every.total_seconds() == 30.0

    def test_check_disruptions_task_name(self):
        """Test that task points to correct Python path."""
        task_config = celery_app.conf.beat_schedule["check-disruptions-and-alert"]

        assert task_config["task"] == "app.celery.tasks.check_disruptions_and_alert"

    def test_check_disruptions_task_expires(self):
        """Test that task expires after 60 seconds if not picked up."""
        task_config = celery_app.conf.beat_schedule["check-disruptions-and-alert"]

        assert "options" in task_config
        assert "expires" in task_config["options"]
        assert task_config["options"]["expires"] == 60

    def test_beat_schedule_structure_integrity(self):
        """Test that all registered tasks have required configuration keys."""
        for task_name, task_config in celery_app.conf.beat_schedule.items():
            # Every scheduled task must have these keys
            assert "task" in task_config, f"{task_name} missing 'task' key"
            assert "schedule" in task_config, f"{task_name} missing 'schedule' key"

            # Verify values are not None or empty
            assert task_config["task"], f"{task_name} has empty 'task' value"
            assert task_config["schedule"], f"{task_name} has empty 'schedule' value"

            # Verify task name is a valid Python path (has at least one dot)
            assert "." in task_config["task"], f"{task_name} task path '{task_config['task']}' invalid"


class TestCeleryAppConfiguration:
    """Test that Celery app is properly configured."""

    def test_celery_app_exists(self):
        """Test that celery_app instance is created."""
        assert celery_app is not None
        assert hasattr(celery_app, "conf")

    def test_broker_url_configured(self):
        """Test that Redis broker URL is configured."""
        assert celery_app.conf.broker_url is not None
        assert len(celery_app.conf.broker_url) > 0
        # Should be redis:// URL
        assert celery_app.conf.broker_url.startswith("redis://")

    def test_result_backend_configured(self):
        """Test that Redis result backend is configured."""
        assert celery_app.conf.result_backend is not None
        assert len(celery_app.conf.result_backend) > 0
        # Should be redis:// URL
        assert celery_app.conf.result_backend.startswith("redis://")

    def test_task_time_limits_configured(self):
        """Test that task time limits are set correctly."""
        # Hard limit: 5 minutes (300 seconds)
        assert celery_app.conf.task_time_limit == 300

        # Soft limit: 4 minutes (240 seconds)
        assert celery_app.conf.task_soft_time_limit == 240

        # Soft limit should be less than hard limit
        assert celery_app.conf.task_soft_time_limit < celery_app.conf.task_time_limit
