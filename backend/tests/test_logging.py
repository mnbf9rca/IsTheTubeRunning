"""Tests for logging configuration module."""

import logging
import sys
from io import StringIO
from unittest.mock import patch

import structlog
from app.core.logging import configure_logging


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
