"""Tests for logging configuration module."""

import logging
import sys
from io import StringIO
from unittest.mock import MagicMock, patch

import structlog
from app.core.logging import _add_otel_context, configure_logging
from opentelemetry import trace


class TestConfigureLogging:
    """Tests for configure_logging function."""

    def test_configure_logging_sets_log_level(self) -> None:
        """Test that configure_logging sets the root logger level."""
        configure_logging(log_level="DEBUG")
        assert logging.getLogger().level == logging.DEBUG

        configure_logging(log_level="WARNING")
        assert logging.getLogger().level == logging.WARNING

        configure_logging(log_level="ERROR")
        assert logging.getLogger().level == logging.ERROR

    def test_configure_logging_default_level_is_info(self) -> None:
        """Test that default log level is INFO."""
        configure_logging()
        assert logging.getLogger().level == logging.INFO

    def test_configure_logging_case_insensitive(self) -> None:
        """Test that log level is case insensitive."""
        configure_logging(log_level="info")
        assert logging.getLogger().level == logging.INFO

        configure_logging(log_level="Debug")
        assert logging.getLogger().level == logging.DEBUG

    def test_configure_logging_sets_noisy_loggers_to_warning(self) -> None:
        """Test that noisy third-party loggers are set to WARNING level."""
        configure_logging(log_level="DEBUG")

        # These should be set to WARNING even when root is DEBUG
        assert logging.getLogger("aiocache").level == logging.WARNING
        assert logging.getLogger("urllib3").level == logging.WARNING
        assert logging.getLogger("urllib3.connectionpool").level == logging.WARNING
        assert logging.getLogger("celery.app.trace").level == logging.WARNING

    def test_configure_logging_clears_existing_handlers(self) -> None:
        """Test that configure_logging clears existing root logger handlers."""
        # Add a dummy handler
        root_logger = logging.getLogger()
        dummy_handler = logging.StreamHandler()
        root_logger.addHandler(dummy_handler)

        # Configure logging should clear and add handler(s)
        # Disable OTEL to keep test simple (just StreamHandler)
        with patch("app.core.config.settings.OTEL_ENABLED", False):
            configure_logging()

        # Should have removed dummy handler and added new handler
        assert dummy_handler not in root_logger.handlers
        # At least one handler should be present
        assert len(root_logger.handlers) >= 1

    def test_configure_logging_handler_outputs_to_stdout(self) -> None:
        """Test that the StreamHandler outputs to stdout."""
        # Disable OTEL to test just the StreamHandler
        with patch("app.core.config.settings.OTEL_ENABLED", False):
            configure_logging()

        root_logger = logging.getLogger()
        # Find the StreamHandler
        stream_handlers = [h for h in root_logger.handlers if isinstance(h, logging.StreamHandler)]
        assert stream_handlers, "No StreamHandler found in root logger handlers"
        handler = stream_handlers[0]

        assert isinstance(handler, logging.StreamHandler)
        assert handler.stream == sys.stdout

    def test_structlog_logger_works_after_configure(self) -> None:
        """Test that structlog loggers work correctly after configuration."""
        configure_logging(log_level="INFO")

        logger = structlog.get_logger("test")

        # This should not raise any exceptions
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            # Re-configure to use the mocked stdout
            configure_logging(log_level="INFO")
            logger = structlog.get_logger("test")
            logger.info("test_event", key="value")
            output = mock_stdout.getvalue()

            # Should have structured output
            assert "test_event" in output or "info" in output.lower()

    def test_stdlib_logger_routed_through_structlog(self) -> None:
        """Test that stdlib loggers are formatted by structlog."""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            configure_logging(log_level="INFO")

            # Use stdlib logger
            stdlib_logger = logging.getLogger("stdlib_test")
            stdlib_logger.info("stdlib message")

            output = mock_stdout.getvalue()
            # Should have structured output with timestamp
            assert "stdlib_test" in output or "stdlib message" in output


class TestConfigureLoggingIdempotent:
    """Tests for idempotent behavior of configure_logging."""

    def test_configure_logging_can_be_called_multiple_times(self) -> None:
        """Test that configure_logging can be called multiple times without error."""
        # Disable OTEL to keep handler count predictable
        with patch("app.core.config.settings.OTEL_ENABLED", False):
            configure_logging(log_level="INFO")
            configure_logging(log_level="DEBUG")
            configure_logging(log_level="WARNING")

        # Should have expected handlers (at least StreamHandler)
        assert len(logging.getLogger().handlers) >= 1
        # Should be at the last configured level
        assert logging.getLogger().level == logging.WARNING


class TestAddOtelContext:
    """Tests for _add_otel_context processor."""

    def test_adds_trace_and_span_ids_with_active_span(self) -> None:
        """Test that trace_id and span_id are added when there is an active span."""
        # Mock the span context
        mock_span_context = MagicMock()
        mock_span_context.trace_id = 0x1234567890ABCDEF1234567890ABCDEF
        mock_span_context.span_id = 0x1234567890ABCDEF

        # Mock the span
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        mock_span.get_span_context.return_value = mock_span_context

        with patch.object(trace, "get_current_span", return_value=mock_span):
            event_dict: dict[str, str] = {"event": "test_event"}
            result = _add_otel_context(logging.getLogger(), "info", event_dict)

            # Should have trace_id and span_id
            assert "trace_id" in result
            assert "span_id" in result
            # Should be 32 and 16 character hex strings
            assert len(result["trace_id"]) == 32
            assert len(result["span_id"]) == 16
            # Should match the expected values
            assert result["trace_id"] == "1234567890abcdef1234567890abcdef"
            assert result["span_id"] == "1234567890abcdef"

    def test_no_trace_ids_without_active_span(self) -> None:
        """Test that trace_id and span_id are not added when there is no active span."""
        # Mock a non-recording span (default when no span is active)
        mock_span = MagicMock()
        mock_span.is_recording.return_value = False

        with patch.object(trace, "get_current_span", return_value=mock_span):
            event_dict: dict[str, str] = {"event": "test_event"}
            result = _add_otel_context(logging.getLogger(), "info", event_dict)

            # Should not have trace_id or span_id (no active span)
            assert "trace_id" not in result
            assert "span_id" not in result
            # Original event should be preserved
            assert result["event"] == "test_event"

    def test_no_trace_ids_with_none_span(self) -> None:
        """Test that trace_id and span_id are not added when span is None."""
        with patch.object(trace, "get_current_span", return_value=None):
            event_dict: dict[str, str] = {"event": "test_event"}
            result = _add_otel_context(logging.getLogger(), "info", event_dict)

            # Should not have trace_id or span_id
            assert "trace_id" not in result
            assert "span_id" not in result
            # Original event should be preserved
            assert result["event"] == "test_event"

    def test_preserves_existing_event_dict_fields(self) -> None:
        """Test that existing event dict fields are preserved."""
        # Mock the span context
        mock_span_context = MagicMock()
        mock_span_context.trace_id = 0xABCDEF1234567890ABCDEF1234567890
        mock_span_context.span_id = 0xABCDEF12345678

        # Mock the span
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        mock_span.get_span_context.return_value = mock_span_context

        with patch.object(trace, "get_current_span", return_value=mock_span):
            event_dict: dict[str, str | int] = {
                "event": "test_event",
                "user_id": "123",
                "action": "login",
                "count": 42,
            }
            result = _add_otel_context(logging.getLogger(), "info", event_dict)

            # Original fields should be preserved
            assert result["event"] == "test_event"
            assert result["user_id"] == "123"
            assert result["action"] == "login"
            assert result["count"] == 42
            # And trace context should be added
            assert "trace_id" in result
            assert "span_id" in result


class TestOTELLoggingHandler:
    """Tests for OTLP LoggingHandler integration."""

    def test_logging_handler_added_when_otel_enabled(self) -> None:
        """Test that LoggingHandler is added when OTEL is enabled."""
        with (
            patch("app.core.config.settings.OTEL_ENABLED", True),
            patch("app.core.config.settings.OTEL_LOG_LEVEL", "INFO"),
            patch("app.core.config.settings.OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", "http://localhost:4318/v1/logs"),
            patch("app.core.telemetry.get_logger_provider") as mock_get_provider,
        ):
            # Mock logger provider
            mock_provider = MagicMock()
            mock_get_provider.return_value = mock_provider

            # Configure logging
            configure_logging(log_level="INFO")

            # Check that both expected handler types are present (resilient to future changes)
            root_logger = logging.getLogger()
            handler_types = [type(h).__name__ for h in root_logger.handlers]
            assert "StreamHandler" in handler_types, "StreamHandler should be present"
            assert "AttrFilteredLoggingHandler" in handler_types, (
                "AttrFilteredLoggingHandler should be present when OTEL enabled"
            )

    def test_logging_handler_not_added_when_otel_disabled(self) -> None:
        """Test that LoggingHandler is NOT added when OTEL is disabled."""
        with patch("app.core.config.settings.OTEL_ENABLED", False):
            # Configure logging
            configure_logging(log_level="INFO")

            # Check that StreamHandler is present and OTEL handler is not
            root_logger = logging.getLogger()
            handler_types = [type(h).__name__ for h in root_logger.handlers]

            assert "StreamHandler" in handler_types, "StreamHandler should be present"
            assert "AttrFilteredLoggingHandler" not in handler_types, (
                "AttrFilteredLoggingHandler should NOT be present when OTEL disabled"
            )

            # Verify StreamHandler outputs to stdout
            stream_handler = next(h for h in root_logger.handlers if isinstance(h, logging.StreamHandler))
            assert stream_handler.stream == sys.stdout

    def test_logging_handler_not_added_when_no_logger_provider(self) -> None:
        """Test that LoggingHandler is not added when get_logger_provider returns None."""
        with (
            patch("app.core.config.settings.OTEL_ENABLED", True),
            patch("app.core.telemetry.get_logger_provider", return_value=None),
        ):
            # Configure logging
            configure_logging(log_level="INFO")

            # Check that only StreamHandler is present (LoggerProvider returned None)
            root_logger = logging.getLogger()
            handler_types = [type(h).__name__ for h in root_logger.handlers]

            assert "StreamHandler" in handler_types, "StreamHandler should be present"
            assert "AttrFilteredLoggingHandler" not in handler_types, (
                "AttrFilteredLoggingHandler should NOT be present when logger provider is None"
            )

    def test_logging_handler_level_matches_otel_log_level(self) -> None:
        """Test that LoggingHandler level matches OTEL_LOG_LEVEL setting."""
        with (
            patch("app.core.config.settings.OTEL_ENABLED", True),
            patch("app.core.config.settings.OTEL_LOG_LEVEL", "WARNING"),
            patch("app.core.config.settings.OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", "http://localhost:4318/v1/logs"),
            patch("app.core.telemetry.get_logger_provider") as mock_get_provider,
        ):
            # Mock logger provider
            mock_provider = MagicMock()
            mock_get_provider.return_value = mock_provider

            # Configure logging
            configure_logging(log_level="INFO")

            # Find the OTEL handler using next()
            root_logger = logging.getLogger()
            otel_handler = next(
                (h for h in root_logger.handlers if type(h).__name__ == "AttrFilteredLoggingHandler"),
                None,
            )

            # Should have found the handler
            assert otel_handler is not None, "AttrFilteredLoggingHandler not found in root logger handlers"
            # Level should match OTEL_LOG_LEVEL (WARNING)
            assert otel_handler.level == logging.WARNING

    def test_logging_handler_with_notset_level(self) -> None:
        """Test that LoggingHandler works with NOTSET level (exports all logs)."""
        with (
            patch("app.core.config.settings.OTEL_ENABLED", True),
            patch("app.core.config.settings.OTEL_LOG_LEVEL", "NOTSET"),
            patch("app.core.config.settings.OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", "http://localhost:4318/v1/logs"),
            patch("app.core.telemetry.get_logger_provider") as mock_get_provider,
        ):
            # Mock logger provider
            mock_provider = MagicMock()
            mock_get_provider.return_value = mock_provider

            # Configure logging
            configure_logging(log_level="DEBUG")

            # Find the OTEL handler using next()
            root_logger = logging.getLogger()
            otel_handler = next(
                (h for h in root_logger.handlers if type(h).__name__ == "AttrFilteredLoggingHandler"),
                None,
            )

            # Should have found the handler
            assert otel_handler is not None, "AttrFilteredLoggingHandler not found in root logger handlers"
            # Level should be NOTSET (0)
            assert otel_handler.level == logging.NOTSET
