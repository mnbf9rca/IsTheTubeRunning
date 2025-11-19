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

        # Configure logging should clear and add exactly one handler
        configure_logging()

        assert len(root_logger.handlers) == 1
        assert dummy_handler not in root_logger.handlers

    def test_configure_logging_handler_outputs_to_stdout(self) -> None:
        """Test that the handler outputs to stdout."""
        configure_logging()

        root_logger = logging.getLogger()
        assert len(root_logger.handlers) == 1
        handler = root_logger.handlers[0]

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
        configure_logging(log_level="INFO")
        configure_logging(log_level="DEBUG")
        configure_logging(log_level="WARNING")

        # Should only have one handler
        assert len(logging.getLogger().handlers) == 1
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
