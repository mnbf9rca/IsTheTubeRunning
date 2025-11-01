# IsTheTubeRunning - Backend

FastAPI backend for the TfL Disruption Alert System.

## Setup

```bash
# Install dependencies
uv sync

# Run development server
uv run uvicorn app.main:app --reload
```

## Testing

```bash
# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov
```

## Linting & Type Checking

```bash
# Format code
uv run ruff format .

# Lint code
uv run ruff check .

# Type check
uv run mypy app
```
