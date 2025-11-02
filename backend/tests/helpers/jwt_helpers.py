"""JWT helper utilities for testing."""

import base64
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlunparse

from app.core.config import settings
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt


class MockJWTGenerator:
    """
    Generate mock JWTs using RS256 for local development and testing.

    This uses the same RS256 algorithm as Auth0, so it tests the same
    code path. Generates ephemeral RSA keys per test run.
    """

    _private_key: Any | None = None
    _public_key: Any | None = None
    _jwks: dict[str, Any] | None = None
    KID = "test-key-1"

    @classmethod
    def _ensure_keys(cls) -> None:
        """
        Generate RSA key pair if not already generated.

        Keys are cached for the duration of the test run.
        """
        if cls._private_key is not None:
            return

        # Generate RSA key pair
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())

        # Store private key in PEM format
        cls._private_key = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()

        # Store public key for JWKS
        public_key = private_key.public_key()
        public_numbers = public_key.public_numbers()

        # Convert to base64url for JWKS
        def int_to_base64url(num: int) -> str:
            """Convert integer to base64url-encoded string."""
            byte_length = (num.bit_length() + 7) // 8
            num_bytes = num.to_bytes(byte_length, byteorder="big")
            return base64.urlsafe_b64encode(num_bytes).decode().rstrip("=")

        n = int_to_base64url(public_numbers.n)
        e = int_to_base64url(public_numbers.e)

        # Create JWKS
        cls._jwks = {
            "keys": [
                {
                    "kty": "RSA",
                    "kid": cls.KID,
                    "use": "sig",
                    "n": n,
                    "e": e,
                }
            ]
        }

    @classmethod
    def generate(
        cls,
        auth0_id: str,
        expires_in: timedelta = timedelta(days=1),
    ) -> str:
        """
        Generate a mock JWT token signed with RS256.

        Args:
            auth0_id: Auth0 user ID (usually format: 'auth0|...')
            expires_in: Token expiration duration

        Returns:
            Mock JWT token string signed with RS256
        """
        cls._ensure_keys()

        now = datetime.now(UTC)

        # Build issuer URL using urllib for proper escaping
        domain = settings.AUTH0_DOMAIN or "test.auth0.com"
        issuer = urlunparse(("https", domain, "/", "", "", ""))

        payload = {
            "sub": auth0_id,
            "iat": int(now.timestamp()),
            "exp": int((now + expires_in).timestamp()),
            "aud": settings.AUTH0_API_AUDIENCE or "test-audience",
            "iss": issuer,
        }

        # _ensure_keys() guarantees _private_key is not None
        assert cls._private_key is not None, "Private key must be initialized"
        return jwt.encode(payload, cls._private_key, algorithm="RS256", headers={"kid": cls.KID})

    @classmethod
    def get_mock_jwks(cls) -> dict[str, Any]:
        """
        Get mock JWKS for testing.

        Returns:
            JWKS dictionary with test public key
        """
        cls._ensure_keys()
        return cls._jwks  # type: ignore[return-value]
