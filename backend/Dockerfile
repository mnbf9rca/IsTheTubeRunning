# Backend Dockerfile for IsTheTubeRunning
FROM python:3.14-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install uv for package management
RUN pip install --no-cache-dir uv

# Copy pyproject.toml and lock file
COPY pyproject.toml ./
COPY uv.lock ./

# Install Python dependencies using uv
RUN uv sync --frozen

# Copy application code
COPY . .

# Set Python path
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Default command (can be overridden in docker-compose)
CMD ["uv", "run", "fastapi", "dev", "app/main.py", "--host", "0.0.0.0", "--port", "8000"]
