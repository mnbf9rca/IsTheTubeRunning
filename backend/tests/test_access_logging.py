"""Tests for access logging middleware."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.middleware.access_logging import AccessLoggingMiddleware
from starlette.requests import Request
from starlette.responses import Response


class TestAccessLoggingMiddleware:
    """Tests for AccessLoggingMiddleware."""

    @pytest.fixture
    def middleware(self) -> AccessLoggingMiddleware:
        """Create middleware instance."""
        app = MagicMock()
        return AccessLoggingMiddleware(app)

    @pytest.fixture
    def mock_request(self) -> MagicMock:
        """Create mock request."""
        request = MagicMock(spec=Request)
        request.method = "GET"
        request.url.path = "/api/v1/test"
        request.client.host = "127.0.0.1"
        request.headers = {}
        return request

    @pytest.mark.asyncio
    async def test_logs_request_with_structlog(
        self, middleware: AccessLoggingMiddleware, mock_request: MagicMock
    ) -> None:
        """Test that middleware logs requests using structlog."""
        response = Response(status_code=200)
        call_next = AsyncMock(return_value=response)

        with patch("app.middleware.access_logging.logger") as mock_logger:
            result = await middleware.dispatch(mock_request, call_next)

            assert result == response
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert call_args[0][0] == "http_request"
            assert call_args[1]["method"] == "GET"
            assert call_args[1]["path"] == "/api/v1/test"
            assert call_args[1]["status_code"] == 200
            assert "duration_ms" in call_args[1]
            assert call_args[1]["client_ip"] == "127.0.0.1"

    @pytest.mark.asyncio
    async def test_extracts_client_ip_from_forwarded_for(
        self, middleware: AccessLoggingMiddleware, mock_request: MagicMock
    ) -> None:
        """Test that middleware extracts client IP from X-Forwarded-For header."""
        mock_request.headers = {"x-forwarded-for": "203.0.113.195, 70.41.3.18"}
        response = Response(status_code=200)
        call_next = AsyncMock(return_value=response)

        with patch("app.middleware.access_logging.logger") as mock_logger:
            await middleware.dispatch(mock_request, call_next)

            call_args = mock_logger.info.call_args
            assert call_args[1]["client_ip"] == "203.0.113.195"

    @pytest.mark.asyncio
    async def test_handles_missing_client(self, middleware: AccessLoggingMiddleware, mock_request: MagicMock) -> None:
        """Test that middleware handles missing client gracefully."""
        mock_request.client = None
        response = Response(status_code=200)
        call_next = AsyncMock(return_value=response)

        with patch("app.middleware.access_logging.logger") as mock_logger:
            await middleware.dispatch(mock_request, call_next)

            call_args = mock_logger.info.call_args
            assert call_args[1]["client_ip"] == "unknown"

    @pytest.mark.asyncio
    async def test_measures_duration(self, middleware: AccessLoggingMiddleware, mock_request: MagicMock) -> None:
        """Test that middleware measures request duration."""
        response = Response(status_code=200)

        async def slow_handler(request: Request) -> Response:
            await asyncio.sleep(0.01)  # 10ms
            return response

        with patch("app.middleware.access_logging.logger") as mock_logger:
            await middleware.dispatch(mock_request, slow_handler)

            call_args = mock_logger.info.call_args
            duration_ms = call_args[1]["duration_ms"]
            assert duration_ms >= 10  # At least 10ms

    @pytest.mark.asyncio
    async def test_logs_error_status_codes(self, middleware: AccessLoggingMiddleware, mock_request: MagicMock) -> None:
        """Test that middleware logs error status codes."""
        response = Response(status_code=500)
        call_next = AsyncMock(return_value=response)

        with patch("app.middleware.access_logging.logger") as mock_logger:
            await middleware.dispatch(mock_request, call_next)

            call_args = mock_logger.info.call_args
            assert call_args[1]["status_code"] == 500
