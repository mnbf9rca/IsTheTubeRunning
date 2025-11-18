"""Tests for Celery worker OpenTelemetry instrumentation.

Tests cover:
- Worker process initialization with OTEL TracerProvider
- CeleryInstrumentor instrumentation
- SQLAlchemy worker engine instrumentation
- Graceful degradation when OTEL is disabled
- TracerProvider shutdown on worker cleanup
"""

import asyncio
import importlib
from unittest.mock import MagicMock, patch

import app.celery.app as celery_app_module
from app.celery import database as celery_database
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


class TestWorkerOtelInitialization:
    """Tests for OTEL initialization in worker_process_init signal."""

    def test_worker_init_creates_tracer_provider_when_otel_enabled(
        self,
        test_tracer_provider: TracerProvider,
        in_memory_span_exporter: InMemorySpanExporter,
    ) -> None:
        """Test that worker initialization creates TracerProvider when OTEL is enabled."""
        # Reset the worker loop state
        celery_database._worker_loop = None

        with (
            patch.object(celery_database.settings, "OTEL_ENABLED", True),
            patch(
                "app.core.telemetry.get_tracer_provider",
                return_value=test_tracer_provider,
            ) as mock_get_provider,
        ):
            # Call the signal handler
            celery_database.init_worker_resources()

            # Verify get_tracer_provider was called
            mock_get_provider.assert_called_once()

            # Clean up
            if celery_database._worker_loop is not None:
                celery_database._worker_loop.close()
                celery_database._worker_loop = None

    def test_worker_init_skips_otel_when_disabled(self) -> None:
        """Test that worker initialization skips OTEL when disabled."""
        # Reset the worker loop state
        celery_database._worker_loop = None

        with (
            patch.object(celery_database.settings, "OTEL_ENABLED", False),
            patch("app.core.telemetry.get_tracer_provider") as mock_get_provider,
        ):
            # Call the signal handler
            celery_database.init_worker_resources()

            # Verify get_tracer_provider was NOT called
            mock_get_provider.assert_not_called()

            # Clean up
            if celery_database._worker_loop is not None:
                celery_database._worker_loop.close()
                celery_database._worker_loop = None

    def test_worker_init_handles_none_tracer_provider(self) -> None:
        """Test that worker initialization handles None TracerProvider gracefully."""
        # Reset the worker loop state
        celery_database._worker_loop = None

        with (
            patch.object(celery_database.settings, "OTEL_ENABLED", True),
            patch(
                "app.core.telemetry.get_tracer_provider",
                return_value=None,
            ) as mock_get_provider,
        ):
            # Call the signal handler - should not raise
            celery_database.init_worker_resources()

            # Verify get_tracer_provider was called
            mock_get_provider.assert_called_once()

            # Clean up
            if celery_database._worker_loop is not None:
                celery_database._worker_loop.close()
                celery_database._worker_loop = None

    def test_worker_init_is_idempotent(
        self,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Test that calling init_worker_resources multiple times is safe."""
        # Create a loop to simulate already initialized state
        celery_database._worker_loop = asyncio.new_event_loop()

        with (
            patch.object(celery_database.settings, "OTEL_ENABLED", True),
            patch("app.core.telemetry.get_tracer_provider") as mock_get_provider,
        ):
            # Call the signal handler - should return early
            celery_database.init_worker_resources()

            # Verify get_tracer_provider was NOT called (early return)
            mock_get_provider.assert_not_called()

            # Clean up
            celery_database._worker_loop.close()
            celery_database._worker_loop = None


class TestWorkerSqlAlchemyInstrumentation:
    """Tests for SQLAlchemy instrumentation in worker engine creation."""

    def test_get_worker_engine_instruments_sqlalchemy_when_otel_enabled(self) -> None:
        """Test that _get_worker_engine instruments SQLAlchemy when OTEL is enabled."""
        # Reset state
        celery_database._worker_engine = None
        celery_database._worker_sqlalchemy_instrumented = False

        with (
            patch.object(celery_database.settings, "OTEL_ENABLED", True),
            patch("app.celery.database.create_async_engine") as mock_create_engine,
            patch("opentelemetry.instrumentation.sqlalchemy.SQLAlchemyInstrumentor") as mock_instrumentor_class,
        ):
            # Setup mock engine
            mock_engine = MagicMock()
            mock_engine.sync_engine = MagicMock()
            mock_create_engine.return_value = mock_engine

            # Setup mock instrumentor
            mock_instrumentor = MagicMock()
            mock_instrumentor_class.return_value = mock_instrumentor

            # Call _get_worker_engine
            engine = celery_database._get_worker_engine()

            # Verify engine was created
            assert engine == mock_engine

            # Verify SQLAlchemyInstrumentor was called
            mock_instrumentor.instrument.assert_called_once_with(engine=mock_engine.sync_engine)

            # Verify flag was set
            assert celery_database._worker_sqlalchemy_instrumented is True

            # Clean up
            celery_database._worker_engine = None
            celery_database._worker_sqlalchemy_instrumented = False

    def test_get_worker_engine_skips_instrumentation_when_otel_disabled(self) -> None:
        """Test that _get_worker_engine skips instrumentation when OTEL is disabled."""
        # Reset state
        celery_database._worker_engine = None
        celery_database._worker_sqlalchemy_instrumented = False

        with (
            patch.object(celery_database.settings, "OTEL_ENABLED", False),
            patch("app.celery.database.create_async_engine") as mock_create_engine,
            patch("opentelemetry.instrumentation.sqlalchemy.SQLAlchemyInstrumentor") as mock_instrumentor_class,
        ):
            # Setup mock engine
            mock_engine = MagicMock()
            mock_create_engine.return_value = mock_engine

            # Call _get_worker_engine
            engine = celery_database._get_worker_engine()

            # Verify engine was created
            assert engine == mock_engine

            # Verify SQLAlchemyInstrumentor was NOT called
            mock_instrumentor_class.assert_not_called()

            # Verify flag was not set
            assert celery_database._worker_sqlalchemy_instrumented is False

            # Clean up
            celery_database._worker_engine = None

    def test_get_worker_engine_instruments_only_once(self) -> None:
        """Test that SQLAlchemy instrumentation only happens once."""
        # Reset state and pre-set the flag
        celery_database._worker_engine = None
        celery_database._worker_sqlalchemy_instrumented = True

        with (
            patch.object(celery_database.settings, "OTEL_ENABLED", True),
            patch("app.celery.database.create_async_engine") as mock_create_engine,
            patch("opentelemetry.instrumentation.sqlalchemy.SQLAlchemyInstrumentor") as mock_instrumentor_class,
        ):
            # Setup mock engine
            mock_engine = MagicMock()
            mock_engine.sync_engine = MagicMock()
            mock_create_engine.return_value = mock_engine

            # Call _get_worker_engine
            celery_database._get_worker_engine()

            # Verify SQLAlchemyInstrumentor was NOT called (already instrumented)
            mock_instrumentor_class.assert_not_called()

            # Clean up
            celery_database._worker_engine = None
            celery_database._worker_sqlalchemy_instrumented = False


class TestWorkerOtelShutdown:
    """Tests for OTEL shutdown in worker cleanup."""

    def test_cleanup_shuts_down_tracer_provider_when_otel_enabled(self) -> None:
        """Test that worker cleanup shuts down TracerProvider when OTEL is enabled."""
        # Setup worker loop
        loop = asyncio.new_event_loop()
        celery_database._worker_loop = loop

        with (
            patch.object(celery_database.settings, "OTEL_ENABLED", True),
            patch("app.core.telemetry.shutdown_tracer_provider") as mock_shutdown,
        ):
            # Call the cleanup handler
            celery_database.cleanup_worker_resources()

            # Verify shutdown was called
            mock_shutdown.assert_called_once()

            # Verify loop was closed
            assert celery_database._worker_loop is None

    def test_cleanup_skips_shutdown_when_otel_disabled(self) -> None:
        """Test that worker cleanup skips OTEL shutdown when disabled."""
        # Setup worker loop
        loop = asyncio.new_event_loop()
        celery_database._worker_loop = loop

        with (
            patch.object(celery_database.settings, "OTEL_ENABLED", False),
            patch("app.core.telemetry.shutdown_tracer_provider") as mock_shutdown,
        ):
            # Call the cleanup handler
            celery_database.cleanup_worker_resources()

            # Verify shutdown was NOT called
            mock_shutdown.assert_not_called()

            # Verify loop was closed
            assert celery_database._worker_loop is None

    def test_cleanup_resets_instrumentation_flag(self) -> None:
        """Test that worker cleanup resets the SQLAlchemy instrumentation flag."""
        # Setup worker loop and set the flag
        loop = asyncio.new_event_loop()
        celery_database._worker_loop = loop
        celery_database._worker_sqlalchemy_instrumented = True

        with patch.object(celery_database.settings, "OTEL_ENABLED", False):
            # Call the cleanup handler
            celery_database.cleanup_worker_resources()

            # Verify flag was reset
            assert celery_database._worker_sqlalchemy_instrumented is False


class TestCeleryAppInstrumentation:
    """Tests for CeleryInstrumentor in app.py."""

    def test_celery_instrumentor_called_when_otel_enabled(self) -> None:
        """Test that CeleryInstrumentor is called when OTEL is enabled."""
        with (
            patch("app.core.config.settings.OTEL_ENABLED", True),
            patch("opentelemetry.instrumentation.celery.CeleryInstrumentor") as mock_instrumentor_class,
        ):
            # Setup mock instrumentor
            mock_instrumentor = MagicMock()
            mock_instrumentor_class.return_value = mock_instrumentor

            # Re-import to trigger the instrumentation code
            # This is a bit hacky but necessary to test module-level code
            importlib.reload(celery_app_module)

            # Verify CeleryInstrumentor was called
            mock_instrumentor.instrument.assert_called()

    def test_celery_instrumentor_not_called_when_otel_disabled(self) -> None:
        """Test that CeleryInstrumentor is not called when OTEL is disabled."""
        with (
            patch("app.core.config.settings.OTEL_ENABLED", False),
            patch("opentelemetry.instrumentation.celery.CeleryInstrumentor") as mock_instrumentor_class,
        ):
            # Re-import to trigger the instrumentation code
            importlib.reload(celery_app_module)

            # Verify CeleryInstrumentor was NOT called
            mock_instrumentor_class.assert_not_called()


class TestWorkerOtelForkSafety:
    """Tests for fork-safety of OTEL initialization."""

    def test_each_worker_gets_own_tracer_provider(
        self,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Test that each worker process gets its own TracerProvider instance."""
        # This simulates what happens after fork - each worker should create
        # its own TracerProvider via get_tracer_provider()

        # Reset state to simulate fresh forked process
        celery_database._worker_loop = None

        with (
            patch.object(celery_database.settings, "OTEL_ENABLED", True),
            patch(
                "app.core.telemetry.get_tracer_provider",
                return_value=test_tracer_provider,
            ),
        ):
            # First worker init
            celery_database.init_worker_resources()

            # Verify get_tracer_provider was called (we can't check global provider
            # because OTEL doesn't allow override)

            # Clean up first worker
            if celery_database._worker_loop is not None:
                celery_database._worker_loop.close()
                celery_database._worker_loop = None

        # Create a second TracerProvider to simulate second worker
        second_provider = TracerProvider(resource=Resource(attributes={"service.name": "worker-2"}))

        with (
            patch.object(celery_database.settings, "OTEL_ENABLED", True),
            patch(
                "app.core.telemetry.get_tracer_provider",
                return_value=second_provider,
            ) as mock_get_provider,
        ):
            # Second worker init
            celery_database.init_worker_resources()

            # Verify get_tracer_provider was called for the second worker
            mock_get_provider.assert_called_once()

            # Clean up
            if celery_database._worker_loop is not None:
                celery_database._worker_loop.close()
                celery_database._worker_loop = None

    def test_worker_engine_instrumentation_is_per_process(self) -> None:
        """Test that SQLAlchemy instrumentation state is per-process."""
        # Reset state to simulate fresh forked process
        celery_database._worker_engine = None
        celery_database._worker_sqlalchemy_instrumented = False

        with (
            patch.object(celery_database.settings, "OTEL_ENABLED", True),
            patch("app.celery.database.create_async_engine") as mock_create_engine,
            patch("opentelemetry.instrumentation.sqlalchemy.SQLAlchemyInstrumentor") as mock_instrumentor_class,
        ):
            # Setup mock engine
            mock_engine = MagicMock()
            mock_engine.sync_engine = MagicMock()
            mock_create_engine.return_value = mock_engine

            # Setup mock instrumentor
            mock_instrumentor = MagicMock()
            mock_instrumentor_class.return_value = mock_instrumentor

            # First access
            celery_database._get_worker_engine()
            assert celery_database._worker_sqlalchemy_instrumented is True

            # Cleanup simulating worker shutdown
            celery_database._worker_engine = None
            celery_database._worker_sqlalchemy_instrumented = False

            # Second access (simulating new worker process)
            mock_create_engine.reset_mock()
            mock_instrumentor.reset_mock()

            celery_database._get_worker_engine()

            # Verify instrumentation was called again for the new "process"
            assert celery_database._worker_sqlalchemy_instrumented is True
            mock_instrumentor.instrument.assert_called_once()

            # Clean up
            celery_database._worker_engine = None
            celery_database._worker_sqlalchemy_instrumented = False
