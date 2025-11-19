"""Tests for Redis OpenTelemetry instrumentation.

Tests cover:
- Redis instrumentation when OTEL is enabled
- Graceful skip when OTEL is disabled
- Instrumentation called only once (idempotent)
"""

from unittest.mock import MagicMock, patch

from app.core import telemetry as telemetry_module


class TestRedisInstrumentation:
    """Tests for RedisInstrumentor in telemetry module."""

    def test_redis_instrumentor_called_when_otel_enabled(self) -> None:
        """Test that RedisInstrumentor is called when OTEL is enabled."""
        # Reset module state
        telemetry_module._tracer_provider = None
        telemetry_module._redis_instrumented = False

        with (
            patch.object(telemetry_module.settings, "OTEL_ENABLED", True),
            patch.object(telemetry_module.settings, "DEBUG", True),  # Skip endpoint requirement
            patch.object(telemetry_module.settings, "OTEL_SERVICE_NAME", "test-service"),
            patch.object(telemetry_module.settings, "OTEL_ENVIRONMENT", "test"),
            patch.object(telemetry_module.settings, "OTEL_EXPORTER_OTLP_ENDPOINT", ""),
            patch.object(telemetry_module, "RedisInstrumentor") as mock_redis_instrumentor_class,
        ):
            # Setup mock instrumentor
            mock_instrumentor = MagicMock()
            mock_redis_instrumentor_class.return_value = mock_instrumentor

            # Call get_tracer_provider which triggers _create_tracer_provider
            provider = telemetry_module.get_tracer_provider()

            # Verify provider was created
            assert provider is not None

            # Verify RedisInstrumentor was called
            mock_instrumentor.instrument.assert_called_once()

            # Verify flag was set
            assert telemetry_module._redis_instrumented

            # Clean up
            telemetry_module._tracer_provider = None
            telemetry_module._redis_instrumented = False

    def test_redis_instrumentor_not_called_when_otel_disabled(self) -> None:
        """Test that RedisInstrumentor is not called when OTEL is disabled."""
        # Reset module state
        telemetry_module._tracer_provider = None
        telemetry_module._redis_instrumented = False

        with (
            patch.object(telemetry_module.settings, "OTEL_ENABLED", False),
            patch.object(telemetry_module, "RedisInstrumentor") as mock_redis_instrumentor_class,
        ):
            # Call get_tracer_provider
            provider = telemetry_module.get_tracer_provider()

            # Verify provider was not created
            assert provider is None

            # Verify RedisInstrumentor was NOT called
            mock_redis_instrumentor_class.assert_not_called()

            # Verify flag was not set
            assert not telemetry_module._redis_instrumented

    def test_redis_instrumentor_called_only_once(self) -> None:
        """Test that RedisInstrumentor is only called once (idempotent)."""
        # Reset module state and pre-set the flag
        telemetry_module._tracer_provider = None
        telemetry_module._redis_instrumented = True

        with (
            patch.object(telemetry_module.settings, "OTEL_ENABLED", True),
            patch.object(telemetry_module.settings, "DEBUG", True),
            patch.object(telemetry_module.settings, "OTEL_SERVICE_NAME", "test-service"),
            patch.object(telemetry_module.settings, "OTEL_ENVIRONMENT", "test"),
            patch.object(telemetry_module.settings, "OTEL_EXPORTER_OTLP_ENDPOINT", ""),
            patch.object(telemetry_module, "RedisInstrumentor") as mock_redis_instrumentor_class,
        ):
            # Call get_tracer_provider
            telemetry_module.get_tracer_provider()

            # Verify RedisInstrumentor was NOT called (already instrumented)
            mock_redis_instrumentor_class.assert_not_called()

            # Clean up
            telemetry_module._tracer_provider = None
            telemetry_module._redis_instrumented = False

    def test_redis_instrumentation_happens_during_provider_creation(self) -> None:
        """Test that Redis instrumentation happens in _create_tracer_provider."""
        # Reset module state
        telemetry_module._tracer_provider = None
        telemetry_module._redis_instrumented = False

        with (
            patch.object(telemetry_module.settings, "OTEL_ENABLED", True),
            patch.object(telemetry_module.settings, "DEBUG", True),
            patch.object(telemetry_module.settings, "OTEL_SERVICE_NAME", "test-service"),
            patch.object(telemetry_module.settings, "OTEL_ENVIRONMENT", "test"),
            patch.object(telemetry_module.settings, "OTEL_EXPORTER_OTLP_ENDPOINT", ""),
            patch.object(telemetry_module, "RedisInstrumentor") as mock_redis_instrumentor_class,
        ):
            # Setup mock instrumentor
            mock_instrumentor = MagicMock()
            mock_redis_instrumentor_class.return_value = mock_instrumentor

            # Directly call _create_tracer_provider
            provider = telemetry_module._create_tracer_provider()

            # Verify provider was created
            assert provider is not None

            # Verify RedisInstrumentor was called
            mock_instrumentor.instrument.assert_called_once()

            # Clean up
            telemetry_module._tracer_provider = None
            telemetry_module._redis_instrumented = False


class TestRedisInstrumentationCoverage:
    """Additional tests for edge cases and coverage."""

    def test_redis_instrumentation_with_otlp_endpoint(self) -> None:
        """Test that Redis instrumentation works with OTLP endpoint configured."""
        # Reset module state
        telemetry_module._tracer_provider = None
        telemetry_module._redis_instrumented = False

        with (
            patch.object(telemetry_module.settings, "OTEL_ENABLED", True),
            patch.object(telemetry_module.settings, "DEBUG", False),
            patch.object(telemetry_module.settings, "OTEL_SERVICE_NAME", "test-service"),
            patch.object(telemetry_module.settings, "OTEL_ENVIRONMENT", "test"),
            patch.object(
                telemetry_module.settings,
                "OTEL_EXPORTER_OTLP_ENDPOINT",
                "http://localhost:4318",
            ),
            patch.object(telemetry_module.settings, "OTEL_EXPORTER_OTLP_HEADERS", ""),
            patch.object(telemetry_module, "RedisInstrumentor") as mock_redis_instrumentor_class,
            patch.object(telemetry_module, "OTLPSpanExporter"),
        ):
            # Setup mock instrumentor
            mock_instrumentor = MagicMock()
            mock_redis_instrumentor_class.return_value = mock_instrumentor

            # Call get_tracer_provider
            provider = telemetry_module.get_tracer_provider()

            # Verify provider was created
            assert provider is not None

            # Verify RedisInstrumentor was called
            mock_instrumentor.instrument.assert_called_once()

            # Verify flag was set
            assert telemetry_module._redis_instrumented

            # Clean up
            telemetry_module._tracer_provider = None
            telemetry_module._redis_instrumented = False

    def test_multiple_get_tracer_provider_calls_instrument_once(self) -> None:
        """Test that multiple calls to get_tracer_provider only instrument once."""
        # Reset module state
        telemetry_module._tracer_provider = None
        telemetry_module._redis_instrumented = False

        with (
            patch.object(telemetry_module.settings, "OTEL_ENABLED", True),
            patch.object(telemetry_module.settings, "DEBUG", True),
            patch.object(telemetry_module.settings, "OTEL_SERVICE_NAME", "test-service"),
            patch.object(telemetry_module.settings, "OTEL_ENVIRONMENT", "test"),
            patch.object(telemetry_module.settings, "OTEL_EXPORTER_OTLP_ENDPOINT", ""),
            patch.object(telemetry_module, "RedisInstrumentor") as mock_redis_instrumentor_class,
        ):
            # Setup mock instrumentor
            mock_instrumentor = MagicMock()
            mock_redis_instrumentor_class.return_value = mock_instrumentor

            # Call get_tracer_provider multiple times
            provider1 = telemetry_module.get_tracer_provider()
            provider2 = telemetry_module.get_tracer_provider()
            provider3 = telemetry_module.get_tracer_provider()

            # Verify same provider returned
            assert provider1 is provider2 is provider3

            # Verify RedisInstrumentor was called only once
            mock_instrumentor.instrument.assert_called_once()

            # Clean up
            telemetry_module._tracer_provider = None
            telemetry_module._redis_instrumented = False
