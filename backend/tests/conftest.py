"""Pytest configuration and fixtures."""

from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """
    Synchronous test client fixture.

    Yields:
        TestClient: FastAPI test client
    """
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """
    Async test client fixture.

    Yields:
        AsyncClient: Async HTTP client
    """
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
def mock_settings() -> dict[str, Any]:
    """
    Mock settings for testing.

    Returns:
        dict: Mock settings
    """
    return {
        "DEBUG": True,
        "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
        "REDIS_URL": "redis://localhost:6379/15",  # Use different DB for tests
    }
