# Backend Dockerfile for IsTheTubeRunning
# Multi-stage build following uv best practices
# See: https://docs.astral.sh/uv/guides/integration/docker/

# Stage 1: Build dependencies
# Use uv's official image with Python 3.14 pre-installed
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

# Enable bytecode compilation for faster startup
# Copy files instead of symlinking to avoid broken links in multi-stage builds
# Use system Python from the base image instead of downloading a new one
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0

# Change the working directory to the `app` directory
WORKDIR /app

# Install dependencies (without installing the project itself yet)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-install-project --no-editable

# Copy the project source code
COPY . /app

# Install the project in non-editable mode
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# Stage 2: Production runtime
# Use matching Python version from official Python images
FROM python:3.14-slim-bookworm

# Accept build commit hash as build arg (defaults to "unknown" for local builds)
ARG BUILD_COMMIT=unknown
ENV BUILD_COMMIT=${BUILD_COMMIT}

WORKDIR /app

# Install runtime dependencies and dotenvx
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    postgresql-client \
    && curl -sfS https://dotenvx.sh/install.sh | sh \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user with home directory
RUN groupadd -r -g 1000 appuser && \
    useradd -r -u 1000 -g appuser -m -d /home/appuser -s /sbin/nologin -c "Application user" appuser && \
    chown -R appuser:appuser /app

# Copy the application and virtual environment from builder
# Both stages use system Python 3.14, so symlinks in .venv/bin work correctly
COPY --from=builder --chown=appuser:appuser /app /app

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

# Switch to non-root user
USER appuser

# Expose non-privileged port
EXPOSE 8000

# Environment variable for configurable worker count
ENV GUNICORN_WORKERS=4

# Environment variable for which .env file to use (default .env for local dev)
ENV DOTENVX_ENV_FILE=.env

# Production command with gunicorn + uvicorn workers
# Wrapped with dotenvx to inject decrypted environment variables
CMD ["/bin/sh", "-c", "exec dotenvx run -f ${DOTENVX_ENV_FILE} -- /app/.venv/bin/python -m gunicorn -k uvicorn.workers.UvicornWorker -w ${GUNICORN_WORKERS} -b 0.0.0.0:8000 app.main:app"]

# Security labels
LABEL security.no_new_privileges="true" \
      security.drop_all_capabilities="true"
