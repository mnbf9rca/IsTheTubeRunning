# Backend Dockerfile for IsTheTubeRunning
# Multi-stage build following uv best practices
# See: https://docs.astral.sh/uv/guides/integration/docker/

# Stage 1: Build dependencies
FROM python:3.14-slim AS builder

# Install build dependencies for compiling Python packages
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Enable bytecode compilation for faster startup
ENV UV_COMPILE_BYTECODE=1

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
FROM python:3.14-slim

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

# Copy the virtual environment from the builder
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Fix broken Python symlinks created by uv in builder stage
# The builder stage symlinks point to /root/.local/share/uv/python which doesn't exist in runtime stage
# Recreate symlinks to point to system Python
RUN rm -f /app/.venv/bin/python /app/.venv/bin/python3 /app/.venv/bin/python3.14 && \
    ln -s /usr/local/bin/python3.14 /app/.venv/bin/python3.14 && \
    ln -s python3.14 /app/.venv/bin/python3 && \
    ln -s python3 /app/.venv/bin/python

# Ensure .venv/bin scripts have execute permissions (only files, not symlinks)
RUN find /app/.venv/bin -type f -exec chmod +x {} \;

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
