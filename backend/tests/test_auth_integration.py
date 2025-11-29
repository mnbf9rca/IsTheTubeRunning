"""Integration tests for authentication API."""

import base64
import json
from collections.abc import AsyncGenerator
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from app.core.database import get_db
from app.main import app
from app.models.admin import AdminUser
from app.models.user import User
from fastapi.testclient import TestClient
from freezegun import freeze_time
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers.jwt_helpers import MockJWTGenerator
from tests.helpers.test_data import make_unique_external_id


class TestAuthReadyEndpoint:
    """Tests for GET /auth/ready endpoint."""

    @pytest.mark.asyncio
    async def test_auth_ready_success(self, db_session: AsyncSession) -> None:
        """Test /auth/ready returns ready=true when database is available."""

        # Override database dependency to use test database
        async def override_get_db() -> AsyncGenerator[AsyncSession]:
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/v1/auth/ready")

                assert response.status_code == 200
                data = response.json()
                assert data["ready"] is True
                assert data.get("message") is None  # No error message
        finally:
            # Clean up override
            app.dependency_overrides.clear()

    def test_auth_ready_no_auth_required(self) -> None:
        """Test /auth/ready does not require authentication."""
        # This endpoint should be accessible without authentication
        # because it's checked before login
        with TestClient(app) as client:
            response = client.get("/api/v1/auth/ready")

            # Should not be 401 or 403
            assert response.status_code != 401
            assert response.status_code != 403

    @pytest.mark.asyncio
    async def test_auth_ready_database_error(self) -> None:
        """Test /auth/ready returns ready=false when database connection fails."""

        # Create a mock session that raises an error
        async def override_get_db_error() -> AsyncGenerator[AsyncSession]:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_session.execute.side_effect = Exception("Database connection failed")
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db_error

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/v1/auth/ready")

                assert response.status_code == 200
                data = response.json()
                assert data["ready"] is False
                assert "Database connection failed" in data["message"]
        finally:
            # Clean up override
            app.dependency_overrides.clear()


class TestAuthMeEndpoint:
    """Tests for GET /auth/me endpoint."""

    def test_get_me_without_auth(self) -> None:
        """Test /auth/me returns 403 without authentication."""
        with TestClient(app) as client:
            response = client.get("/api/v1/auth/me")

            assert response.status_code == 401  # FastAPI 0.122+ returns 401 for missing credentials per RFC 7235
            assert "detail" in response.json()

    def test_get_me_with_invalid_token(self) -> None:
        """Test /auth/me returns 401 with invalid token."""
        headers = {"Authorization": "Bearer invalid.token.here"}

        with TestClient(app) as client:
            response = client.get("/api/v1/auth/me", headers=headers)

            assert response.status_code == 401
            assert "detail" in response.json()

    def test_get_me_with_malformed_authorization_header(self) -> None:
        """Test /auth/me returns 403 with malformed Authorization header."""
        with TestClient(app) as client:
            # Missing 'Bearer' prefix
            headers = {"Authorization": "NotBearerToken"}
            response = client.get("/api/v1/auth/me", headers=headers)
            assert response.status_code == 401  # FastAPI 0.122+ returns 401 for missing credentials per RFC 7235
            assert "detail" in response.json()

    def test_get_me_with_expired_token(self) -> None:
        """Test /auth/me returns 401 with expired JWT token."""
        # Create an expired token using freezegun
        external_id = make_unique_external_id("auth0|expired_test")

        # Generate token in the past
        with freeze_time("2024-01-01 12:00:00"):
            # Token with 1 hour expiration
            expired_token = MockJWTGenerator.generate(auth0_id=external_id, expires_in=timedelta(hours=1))

        # Now we're "in the future" (current time), token should be expired
        headers = {"Authorization": f"Bearer {expired_token}"}

        with TestClient(app) as client:
            response = client.get("/api/v1/auth/me", headers=headers)
            assert response.status_code == 401
            assert "detail" in response.json()
            # Should mention expiration or invalid credentials
            detail_lower = response.json()["detail"].lower()
            assert "invalid" in detail_lower or "expired" in detail_lower

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
                assert "is_admin" in data
                assert data["is_admin"] is False  # New users are not admin by default
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
                assert "is_admin" in data
                assert data["is_admin"] is False  # Regular user is not admin
                assert "external_id" not in data
                assert "auth_provider" not in data
        finally:
            # Clean up override
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_me_returns_admin_true_for_admin_users(
        self, db_session: AsyncSession, admin_user: tuple[User, AdminUser], auth_headers_for_user: dict[str, str]
    ) -> None:
        """Test /auth/me returns is_admin=true for admin users."""
        test_user, _admin_record = admin_user

        # Override database dependency to use test database
        async def override_get_db() -> AsyncGenerator[AsyncSession]:
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/v1/auth/me", headers=auth_headers_for_user)

                assert response.status_code == 200
                data = response.json()
                assert data["id"] == str(test_user.id)
                assert data["is_admin"] is True  # Admin user returns True
                assert "created_at" in data
                assert "updated_at" in data
        finally:
            # Clean up override
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_me_returns_admin_false_for_non_admin_users(
        self, db_session: AsyncSession, test_user: User, auth_headers_for_user: dict[str, str]
    ) -> None:
        """Test /auth/me returns is_admin=false for non-admin users."""
        # test_user fixture is a regular user (not admin)

        # Override database dependency to use test database
        async def override_get_db() -> AsyncGenerator[AsyncSession]:
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/v1/auth/me", headers=auth_headers_for_user)

                assert response.status_code == 200
                data = response.json()
                assert data["id"] == str(test_user.id)
                assert data["is_admin"] is False  # Non-admin user returns False
                assert "created_at" in data
                assert "updated_at" in data
        finally:
            # Clean up override
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_me_response_includes_all_expected_fields(
        self, db_session: AsyncSession, test_user: User, auth_headers_for_user: dict[str, str]
    ) -> None:
        """Test /auth/me response includes all expected fields."""

        # Override database dependency to use test database
        async def override_get_db() -> AsyncGenerator[AsyncSession]:
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/v1/auth/me", headers=auth_headers_for_user)

                assert response.status_code == 200
                data = response.json()

                # Expected fields
                assert "id" in data
                assert "created_at" in data
                assert "updated_at" in data
                assert "is_admin" in data  # NEW field

                # Should NOT include these fields (security)
                assert "external_id" not in data
                assert "auth_provider" not in data
        finally:
            # Clean up override
            app.dependency_overrides.clear()
