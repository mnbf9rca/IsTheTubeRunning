"""Integration tests for authentication API."""

import base64
import json
from collections.abc import AsyncGenerator

import pytest
from app.core.database import get_db
from app.main import app
from app.models.user import User
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import make_unique_external_id
from tests.mock_jwt import MockJWTGenerator


class TestAuthMeEndpoint:
    """Tests for GET /auth/me endpoint."""

    def test_get_me_without_auth(self) -> None:
        """Test /auth/me returns 403 without authentication."""
        with TestClient(app) as client:
            response = client.get("/api/v1/auth/me")

            assert response.status_code == 403
            assert "detail" in response.json()

    def test_get_me_with_invalid_token(self) -> None:
        """Test /auth/me returns 401 with invalid token."""
        headers = {"Authorization": "Bearer invalid.token.here"}

        with TestClient(app) as client:
            response = client.get("/api/v1/auth/me", headers=headers)

            assert response.status_code == 401
            assert "detail" in response.json()

    def test_get_me_with_token_missing_kid(self) -> None:
        """Test /auth/me returns 401 when token missing kid in header."""
        # Create a token without kid in header (manually constructed malformed JWT)
        header = {"alg": "RS256", "typ": "JWT"}  # Missing 'kid'
        payload = {"sub": "auth0|test", "aud": "test-audience", "iss": "https://test.auth0.com/"}

        # Base64url encode without padding
        def b64encode_url(data: dict[str, str]) -> str:
            json_str = json.dumps(data)
            return base64.urlsafe_b64encode(json_str.encode()).decode().rstrip("=")

        malformed_token = f"{b64encode_url(header)}.{b64encode_url(payload)}.fake_signature"
        headers = {"Authorization": f"Bearer {malformed_token}"}

        with TestClient(app) as client:
            response = client.get("/api/v1/auth/me", headers=headers)

            assert response.status_code == 401
            assert "detail" in response.json()
            assert "kid" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_me_with_valid_token_new_user(self, db_session: AsyncSession) -> None:
        """Test /auth/me with valid token creates new user."""
        # Generate valid mock JWT for new user
        auth0_id = make_unique_external_id("auth0|integration_test_new_user")
        token = MockJWTGenerator.generate(auth0_id=auth0_id)
        headers = {"Authorization": f"Bearer {token}"}

        # Override database dependency to use test database
        async def override_get_db() -> AsyncGenerator[AsyncSession]:
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/v1/auth/me", headers=headers)

                assert response.status_code == 200
                data = response.json()
                # API response deliberately excludes external_id and auth_provider for security
                assert "id" in data
                assert "created_at" in data
                assert "updated_at" in data
                assert "external_id" not in data
                assert "auth_provider" not in data
        finally:
            # Clean up override
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_me_with_valid_token_existing_user(self, db_session: AsyncSession) -> None:
        """Test /auth/me with valid token returns existing user."""
        # Create existing user
        auth0_id = make_unique_external_id("auth0|integration_test_existing_user")
        existing_user = User(external_id=auth0_id, auth_provider="auth0")
        db_session.add(existing_user)
        await db_session.commit()
        await db_session.refresh(existing_user)

        # Generate valid mock JWT for existing user
        token = MockJWTGenerator.generate(auth0_id=auth0_id)
        headers = {"Authorization": f"Bearer {token}"}

        # Override database dependency to use test database
        async def override_get_db() -> AsyncGenerator[AsyncSession]:
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/v1/auth/me", headers=headers)

                assert response.status_code == 200
                data = response.json()
                # API response deliberately excludes external_id and auth_provider for security
                assert data["id"] == str(existing_user.id)
                assert "created_at" in data
                assert "updated_at" in data
                assert "external_id" not in data
                assert "auth_provider" not in data
        finally:
            # Clean up override
            app.dependency_overrides.clear()
