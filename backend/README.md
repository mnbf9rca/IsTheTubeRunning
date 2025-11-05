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

### Running All Tests

```bash
# Run all tests (unit + integration)
uv run pytest

# Run tests with coverage
uv run pytest --cov
```

### Integration Tests

Integration tests verify end-to-end functionality by calling the real TfL API. These tests are marked with `@pytest.mark.integration` and require a valid TfL API key.

**Setup for Integration Tests:**

1. Get a TfL API key from https://api.tfl.gov.uk/
2. Add it to your `.env` file:
   ```bash
   TFL_API_KEY=your_actual_api_key_here
   ```

**Running Integration Tests:**

```bash
# Run only integration tests
uv run pytest -m integration

# Run all tests except integration tests
uv run pytest -m "not integration"

# Run specific integration test
uv run pytest tests/test_tfl_integration.py::test_integration_fetch_lines -v
```

**CI/CD:**

Integration tests run automatically in GitHub Actions CI when the `TFL_API_KEY` secret is set. If the API key is not available, tests will gracefully skip with a message.

## Linting & Type Checking

```bash
# Format code
uv run ruff format .

# Lint code
uv run ruff check .

# Type check
uv run mypy app
```
