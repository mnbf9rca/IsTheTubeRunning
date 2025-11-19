"""Access logging middleware using structlog with OTEL trace correlation."""

import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger(__name__)


class AccessLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs HTTP requests with structured data.

    Replaces uvicorn's access logging with structlog-formatted logs
    that include OpenTelemetry trace IDs for correlation.

    Log fields:
        - method: HTTP method (GET, POST, etc.)
        - path: Request path
        - status_code: Response status code
        - duration_ms: Request duration in milliseconds
        - client_ip: Client IP address
        - trace_id/span_id: Automatically added by OTEL processor
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process request and log access information."""
        start_time = time.perf_counter()

        # Get client IP address (direct connection)
        # Note: X-Forwarded-For can be spoofed by clients. In production behind a trusted
        # proxy (e.g., Cloudflare), the forwarded_for value from the first hop is reliable.
        # We log both values for observability - analysis can determine which to trust
        # based on deployment context.
        client_ip = request.client.host if request.client else "unknown"
        forwarded_for = None
        if xff_header := request.headers.get("x-forwarded-for"):
            forwarded_for = xff_header.split(",")[0].strip()

        # Process the request
        response = await call_next(request)

        # Calculate duration
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Log the request with both IP values for full visibility
        log_kwargs: dict[str, str | int | float | None] = {
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
            "client_ip": client_ip,
        }
        if forwarded_for:
            log_kwargs["forwarded_for"] = forwarded_for

        logger.info("http_request", **log_kwargs)

        return response
