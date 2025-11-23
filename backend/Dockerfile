# Backend Dockerfile for IsTheTubeRunning
# Multi-stage build for security and minimal image size
# Uses uv to manage Python - no python base image needed!

# Stage 1: Build dependencies
FROM debian:bookworm-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates \
    gcc \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy uv binary from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install Python (via uv) and dependencies (production only)
RUN uv sync --frozen --no-dev

# Stage 2: Production runtime
FROM debian:bookworm-slim

WORKDIR /app

# Install only runtime dependencies
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r -g 1000 appuser && \
    useradd -r -u 1000 -g appuser -s /sbin/nologin -c "Application user" appuser

# Copy uv binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy Python and installed dependencies from builder
COPY --from=builder --chown=appuser:appuser /root/.local/share/uv/python /root/.local/share/uv/python
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Copy application code
COPY --chown=appuser:appuser . .

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

# Switch to non-root user
USER appuser

# Expose non-privileged port
EXPOSE 8000

# Production command with gunicorn + uvicorn workers
CMD ["uv", "run", "--no-sync", "gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "4", "-b", "0.0.0.0:8000", "app.main:app"]

# Security labels
LABEL security.no_new_privileges="true" \
      security.drop_all_capabilities="true"
