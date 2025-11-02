"""Unit tests for authentication."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from app.core import auth
from app.core.auth import get_current_user, get_jwks, verify_jwt
from app.core.config import settings
from app.models.user import User
from app.services.auth_service import AuthService
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import make_unique_external_id
from tests.mock_jwt import MockJWTGenerator


class TestAuthService:
    """Tests for AuthService."""

    @pytest.mark.asyncio
    async def test_create_user(self, db_session: AsyncSession) -> None:
        """Test creating a new user."""
        auth_service = AuthService(db_session)
        external_id = make_unique_external_id("auth0|new_user")
        user = await auth_service.create_user(external_id=external_id, auth_provider="auth0")

        assert user.id is not None
        assert user.external_id == external_id
        assert user.auth_provider == "auth0"
        assert user.created_at is not None
        assert user.updated_at is not None

    @pytest.mark.asyncio
    async def test_get_user_by_external_id(self, db_session: AsyncSession, test_user: User) -> None:
        """Test retrieving user by external ID."""
        auth_service = AuthService(db_session)
        user = await auth_service.get_user_by_external_id(test_user.external_id, test_user.auth_provider)

        assert user is not None
        assert user.id == test_user.id
        assert user.external_id == test_user.external_id
        assert user.auth_provider == test_user.auth_provider

    @pytest.mark.asyncio
    async def test_get_user_by_external_id_not_found(self, db_session: AsyncSession) -> None:
        """Test retrieving non-existent user returns None."""
        auth_service = AuthService(db_session)
        external_id = make_unique_external_id("auth0|nonexistent")
        user = await auth_service.get_user_by_external_id(external_id, "auth0")

        assert user is None

    @pytest.mark.asyncio
    async def test_get_user_by_id(self, db_session: AsyncSession, test_user: User) -> None:
        """Test retrieving user by UUID."""
        auth_service = AuthService(db_session)
        user = await auth_service.get_user_by_id(test_user.id)

        assert user is not None
        assert user.id == test_user.id
        assert user.external_id == test_user.external_id
        assert user.auth_provider == test_user.auth_provider

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, db_session: AsyncSession) -> None:
        """Test retrieving non-existent user by ID returns None."""
        auth_service = AuthService(db_session)
        user = await auth_service.get_user_by_id(uuid.uuid4())

        assert user is None

    @pytest.mark.asyncio
    async def test_get_or_create_user_existing(self, db_session: AsyncSession, test_user: User) -> None:
        """Test get_or_create returns existing user."""
        auth_service = AuthService(db_session)
        user = await auth_service.get_or_create_user(test_user.external_id, test_user.auth_provider)

        assert user.id == test_user.id
        assert user.external_id == test_user.external_id
        assert user.auth_provider == test_user.auth_provider

    @pytest.mark.asyncio
    async def test_get_or_create_user_new(self, db_session: AsyncSession) -> None:
        """Test get_or_create creates new user if doesn't exist."""
        auth_service = AuthService(db_session)
        external_id = make_unique_external_id("auth0|brand_new_user")
        user = await auth_service.get_or_create_user(external_id, "auth0")

        assert user.id is not None
        assert user.external_id == external_id
        assert user.auth_provider == "auth0"
        assert user.created_at is not None


class TestMockJWTGenerator:
    """Tests for MockJWTGenerator."""

    def test_generate_custom_auth0_id(self) -> None:
        """Test generating mock JWT with custom auth0_id."""
        auth0_id = make_unique_external_id("auth0|custom_user")
        token = MockJWTGenerator.generate(auth0_id=auth0_id)

        # Decode without verification to check payload
        payload = jwt.get_unverified_claims(token)
        assert payload["sub"] == auth0_id

    def test_jwks_generation(self) -> None:
        """Test that JWKS is generated correctly."""
        jwks = MockJWTGenerator.get_mock_jwks()

        assert "keys" in jwks
        assert len(jwks["keys"]) == 1
        key = jwks["keys"][0]
        assert key["kty"] == "RSA"
        assert key["kid"] == MockJWTGenerator.KID
        assert key["use"] == "sig"
        assert "n" in key
        assert "e" in key

    def test_token_has_kid_header(self) -> None:
        """Test that generated token has kid in header."""
        auth0_id = make_unique_external_id("auth0|test_kid_header")
        token = MockJWTGenerator.generate(auth0_id=auth0_id)
        header = jwt.get_unverified_header(token)

        assert "kid" in header
        assert header["kid"] == MockJWTGenerator.KID
        assert header["alg"] == "RS256"

    def test_token_payload_structure(self) -> None:
        """Test that token payload has required claims."""
        auth0_id = make_unique_external_id("auth0|test_payload")
        token = MockJWTGenerator.generate(auth0_id=auth0_id)
        payload = jwt.get_unverified_claims(token)

        assert payload["sub"] == auth0_id
        assert "iat" in payload
        assert "exp" in payload
        assert "aud" in payload
        assert "iss" in payload
        assert isinstance(payload["iat"], int)
        assert isinstance(payload["exp"], int)
        assert payload["exp"] > payload["iat"]


class TestSetMockJWKS:
    """Tests for set_mock_jwks function."""

    def test_set_mock_jwks_raises_when_not_in_debug_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that set_mock_jwks raises RuntimeError when DEBUG=False."""
        # Temporarily set DEBUG to False
        monkeypatch.setattr(settings, "DEBUG", False)

        # Should raise RuntimeError
        with pytest.raises(RuntimeError, match="can only be called in DEBUG mode"):
            auth.set_mock_jwks({"keys": []})

    @pytest.mark.asyncio
    async def test_verify_jwt_raises_when_mock_jwks_not_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that verify_jwt raises HTTPException when DEBUG=True but mock JWKS not set."""
        # Save current state
        original_mock_jwks = auth._mock_jwks

        try:
            # Set DEBUG to True and clear mock JWKS
            monkeypatch.setattr(settings, "DEBUG", True)
            auth._mock_jwks = None

            # Generate a token (this will work because _ensure_keys creates keys)
            token = MockJWTGenerator.generate(auth0_id=make_unique_external_id())
            credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

            # Should raise HTTPException about mock JWKS not configured
            with pytest.raises(HTTPException) as exc_info:
                await verify_jwt(credentials)

            assert exc_info.value.status_code == 500
            assert "mock jwks not configured" in exc_info.value.detail.lower()
        finally:
            # Restore original state
            auth._mock_jwks = original_mock_jwks


class TestVerifyJWTEdgeCases:
    """Tests for verify_jwt edge cases."""

    @pytest.mark.asyncio
    async def test_verify_jwt_with_mismatched_kid(self) -> None:
        """Test verify_jwt fails when token kid doesn't match JWKS."""
        # Generate a token with a different kid
        now = datetime.now(UTC)
        auth0_id = make_unique_external_id("auth0|test_mismatched_kid")
        payload = {
            "sub": auth0_id,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
            "aud": "test-audience",
            "iss": "https://test.auth0.com/",
        }

        # Create token with non-matching kid
        MockJWTGenerator._ensure_keys()
        assert MockJWTGenerator._private_key is not None, "Private key must be initialized"
        token = jwt.encode(
            payload,
            MockJWTGenerator._private_key,
            algorithm="RS256",
            headers={"kid": "non-matching-kid-123"},
        )

        # Verify the token has the wrong kid
        header = jwt.get_unverified_header(token)
        assert header["kid"] != MockJWTGenerator.KID

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        # Should raise HTTPException with 401
        with pytest.raises(HTTPException) as exc_info:
            await verify_jwt(credentials)

        assert exc_info.value.status_code == 401
        assert "signing key" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_get_current_user_with_missing_sub(self, db_session: AsyncSession) -> None:
        """Test get_current_user fails when payload missing 'sub' claim."""
        # Payload without 'sub' claim
        payload = {"iat": 123456, "exp": 999999, "aud": "test-audience"}

        # Should raise HTTPException with 401
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(payload=payload, db=db_session)

        assert exc_info.value.status_code == 401
        assert "sub" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_get_jwks_success(self) -> None:
        """Test get_jwks successfully fetches JWKS from Auth0."""
        mock_jwks = {
            "keys": [
                {
                    "kty": "RSA",
                    "kid": "test-kid",
                    "use": "sig",
                    "n": "test-n",
                    "e": "AQAB",
                }
            ]
        }

        # Mock httpx.AsyncClient
        with patch("app.core.auth.httpx.AsyncClient") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_jwks
            mock_response.raise_for_status.return_value = None

            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__.return_value = mock_client_instance

            result = await get_jwks("test.auth0.com")

            assert result == mock_jwks

    @pytest.mark.asyncio
    async def test_get_jwks_http_error(self, reset_jwks_cache: None) -> None:
        """Test get_jwks handles HTTP errors."""
        # Mock httpx.AsyncClient to raise HTTPError
        with patch("app.core.auth.httpx.AsyncClient") as mock_client_cls:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(side_effect=httpx.HTTPError("Connection failed"))
            mock_client_cls.return_value.__aenter__.return_value = mock_client_instance

            with pytest.raises(HTTPException) as exc_info:
                await get_jwks("test.auth0.com")

            assert exc_info.value.status_code == 503
            assert "unable to fetch jwks" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_get_jwks_uses_cache(self, reset_jwks_cache: None) -> None:
        """Test get_jwks uses cached JWKS within TTL."""
        mock_jwks = {"keys": [{"kid": "cached-key"}]}

        with patch("app.core.auth.httpx.AsyncClient") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_jwks
            mock_response.raise_for_status.return_value = None

            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__.return_value = mock_client_instance

            # First call should fetch from Auth0
            result1 = await get_jwks("test.auth0.com")
            assert result1 == mock_jwks
            assert mock_client_instance.get.call_count == 1

            # Second call should use cache
            result2 = await get_jwks("test.auth0.com")
            assert result2 == mock_jwks
            # Call count should still be 1 (cached)
            assert mock_client_instance.get.call_count == 1
