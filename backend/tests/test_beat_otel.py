"""Tests for Celery Beat OpenTelemetry initialization.

Tests cover:
- Beat process initialization with OTEL TracerProvider
- Graceful skip when OTEL is disabled
- Handling of None TracerProvider
"""

from unittest.mock import MagicMock, patch

import app.celery.app as celery_app_module
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider


class TestBeatOtelInitialization:
    """Tests for OTEL initialization in beat_init signal."""

    def test_beat_init_creates_tracer_provider_when_otel_enabled(self) -> None:
        """Test that beat_init initializes TracerProvider when OTEL is enabled."""
        # Create a test TracerProvider
        test_provider = TracerProvider(resource=Resource(attributes={"service.name": "test-beat"}))

        with (
            patch.object(celery_app_module.settings, "OTEL_ENABLED", True),
            patch(
                "app.core.telemetry.get_tracer_provider",
                return_value=test_provider,
            ) as mock_get_provider,
            patch("opentelemetry.trace.set_tracer_provider") as mock_set_provider,
        ):
            # Call the signal handler
            celery_app_module.init_beat_otel()

            # Verify get_tracer_provider was called
            mock_get_provider.assert_called_once()

            # Verify set_tracer_provider was called with the provider
            mock_set_provider.assert_called_once_with(test_provider)

    def test_beat_init_skips_otel_when_disabled(self) -> None:
        """Test that beat_init skips OTEL initialization when disabled."""
        with (
            patch.object(celery_app_module.settings, "OTEL_ENABLED", False),
            patch("app.core.telemetry.get_tracer_provider") as mock_get_provider,
            patch("opentelemetry.trace.set_tracer_provider") as mock_set_provider,
        ):
            # Call the signal handler
            celery_app_module.init_beat_otel()

            # Verify get_tracer_provider was NOT called
            mock_get_provider.assert_not_called()

            # Verify set_tracer_provider was NOT called
            mock_set_provider.assert_not_called()

    def test_beat_init_handles_none_tracer_provider(self) -> None:
        """Test that beat_init handles None TracerProvider gracefully."""
        with (
            patch.object(celery_app_module.settings, "OTEL_ENABLED", True),
            patch(
                "app.core.telemetry.get_tracer_provider",
                return_value=None,
            ) as mock_get_provider,
            patch("opentelemetry.trace.set_tracer_provider") as mock_set_provider,
        ):
            # Call the signal handler - should not raise
            celery_app_module.init_beat_otel()

            # Verify get_tracer_provider was called
            mock_get_provider.assert_called_once()

            # Verify set_tracer_provider was NOT called (walrus operator returns None)
            mock_set_provider.assert_not_called()

    def test_beat_init_logs_initialization(self) -> None:
        """Test that beat_init logs when TracerProvider and LoggerProvider are initialized."""
        # Create a test TracerProvider
        test_provider = TracerProvider(resource=Resource(attributes={"service.name": "test-beat"}))

        with (
            patch.object(celery_app_module.settings, "OTEL_ENABLED", True),
            patch(
                "app.core.telemetry.get_tracer_provider",
                return_value=test_provider,
            ),
            patch("app.core.telemetry.set_logger_provider"),
            patch("opentelemetry.trace.set_tracer_provider"),
            patch.object(celery_app_module.logger, "info") as mock_logger_info,
        ):
            # Call the signal handler
            celery_app_module.init_beat_otel()

            # Verify logging was called for both providers and build_commit
            assert mock_logger_info.call_count == 3
            mock_logger_info.assert_any_call("beat_otel_tracer_provider_initialized")
            mock_logger_info.assert_any_call("beat_otel_logger_provider_initialized")
            mock_logger_info.assert_any_call(
                "beat_init_completed", build_commit=celery_app_module.settings.BUILD_COMMIT
            )

    def test_beat_init_handles_get_tracer_provider_exception(self) -> None:
        """Test that beat_init handles exception from get_tracer_provider gracefully."""
        with (
            patch.object(celery_app_module.settings, "OTEL_ENABLED", True),
            patch(
                "app.core.telemetry.get_tracer_provider",
                side_effect=Exception("Test get_tracer_provider error"),
            ),
            patch("opentelemetry.trace.set_tracer_provider") as mock_set_provider,
        ):
            # Call the signal handler - should not raise
            celery_app_module.init_beat_otel()

            # Verify set_tracer_provider was NOT called (exception was caught)
            mock_set_provider.assert_not_called()

    def test_beat_init_handles_set_tracer_provider_exception(self) -> None:
        """Test that beat_init handles exception from set_tracer_provider gracefully."""
        test_provider = TracerProvider(resource=Resource(attributes={"service.name": "test-beat"}))
        with (
            patch.object(celery_app_module.settings, "OTEL_ENABLED", True),
            patch(
                "app.core.telemetry.get_tracer_provider",
                return_value=test_provider,
            ),
            patch(
                "opentelemetry.trace.set_tracer_provider",
                side_effect=Exception("Test set_tracer_provider error"),
            ),
        ):
            # Call the signal handler - should not raise
            celery_app_module.init_beat_otel()
            # If we get here, the exception was handled gracefully


class TestBeatOtelForkSafety:
    """Tests for fork-safety of Beat OTEL initialization."""

    def test_beat_init_can_be_called_multiple_times(self) -> None:
        """Test that beat_init is safe to call multiple times."""
        # Create a test TracerProvider
        test_provider = TracerProvider(resource=Resource(attributes={"service.name": "test-beat"}))

        with (
            patch.object(celery_app_module.settings, "OTEL_ENABLED", True),
            patch(
                "app.core.telemetry.get_tracer_provider",
                return_value=test_provider,
            ) as mock_get_provider,
            patch("opentelemetry.trace.set_tracer_provider") as mock_set_provider,
        ):
            # Call the signal handler multiple times
            celery_app_module.init_beat_otel()
            celery_app_module.init_beat_otel()

            # Verify get_tracer_provider was called twice
            assert mock_get_provider.call_count == 2

            # Verify set_tracer_provider was called twice
            assert mock_set_provider.call_count == 2

    def test_beat_gets_own_tracer_provider_instance(self) -> None:
        """Test that Beat process gets its own TracerProvider via get_tracer_provider."""
        # This verifies the pattern used - Beat calls get_tracer_provider() which
        # creates a new provider in the Beat process (fork-safe)

        mock_provider = MagicMock(spec=TracerProvider)

        with (
            patch.object(celery_app_module.settings, "OTEL_ENABLED", True),
            patch(
                "app.core.telemetry.get_tracer_provider",
                return_value=mock_provider,
            ) as mock_get_provider,
            patch("opentelemetry.trace.set_tracer_provider") as mock_set_provider,
        ):
            # Call the signal handler
            celery_app_module.init_beat_otel()

            # Verify the lazy initialization pattern is used
            mock_get_provider.assert_called_once()
            mock_set_provider.assert_called_once_with(mock_provider)


class TestBeatOtelSignalConnection:
    """Tests for beat_init signal connection."""

    def test_beat_init_signal_handler_exists(self) -> None:
        """Test that the beat_init signal handler is defined."""
        # Verify the function exists and has correct signature
        assert hasattr(celery_app_module, "init_beat_otel")
        assert callable(celery_app_module.init_beat_otel)

    def test_beat_init_accepts_kwargs(self) -> None:
        """Test that beat_init accepts arbitrary kwargs (Celery signal pattern)."""
        with (
            patch.object(celery_app_module.settings, "OTEL_ENABLED", False),
        ):
            # Call with extra kwargs - should not raise
            celery_app_module.init_beat_otel(
                sender=None,
                signal=None,
                extra_param="test",
            )
