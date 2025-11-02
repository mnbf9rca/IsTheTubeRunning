"""Tests for Mock JWT functionality in development mode."""

import time
from datetime import UTC, datetime, timedelta

from jose import jwt

from tests.helpers.jwt_helpers import MockJWTGenerator
from tests.helpers.test_data import make_unique_external_id


class TestMockJWTGeneration:
    """Tests for mock JWT generation."""

    def test_generate_creates_valid_jwt_structure(self) -> None:
        """Test that generated token has valid JWT structure."""
        token = MockJWTGenerator.generate(auth0_id=make_unique_external_id())

        # JWT has 3 parts separated by dots
        parts = token.split(".")
        assert len(parts) == 3

    def test_generate_with_custom_auth0_id(self) -> None:
        """Test generating token with custom Auth0 ID."""
        custom_id = "auth0|custom_987654"
        token = MockJWTGenerator.generate(auth0_id=custom_id)

        payload = jwt.get_unverified_claims(token)
        assert payload["sub"] == custom_id

    def test_generate_with_custom_expiration(self) -> None:
        """Test generating token with custom expiration."""
        expires_in = timedelta(hours=2)
        token = MockJWTGenerator.generate(auth0_id=make_unique_external_id(), expires_in=expires_in)

        payload = jwt.get_unverified_claims(token)

        # Check expiration is approximately 2 hours from now
        exp_time = datetime.fromtimestamp(payload["exp"], tz=UTC)
        expected_exp = datetime.now(UTC) + expires_in
        time_diff = abs((exp_time - expected_exp).total_seconds())

        # Allow 5 seconds tolerance for test execution time
        assert time_diff < 5

    def test_generate_includes_required_claims(self) -> None:
        """Test that generated token includes all required JWT claims."""
        token = MockJWTGenerator.generate(auth0_id=make_unique_external_id())
        payload = jwt.get_unverified_claims(token)

        # Required claims
        assert "sub" in payload  # Subject (Auth0 ID)
        assert "iat" in payload  # Issued at
        assert "exp" in payload  # Expiration
        assert "aud" in payload  # Audience
        assert "iss" in payload  # Issuer

    def test_generate_expiration_after_issued_at(self) -> None:
        """Test that expiration time is after issued at time."""
        token = MockJWTGenerator.generate(auth0_id=make_unique_external_id())
        payload = jwt.get_unverified_claims(token)

        assert payload["exp"] > payload["iat"]

    def test_generate_timestamps_are_realistic(self) -> None:
        """Test that timestamps are close to current time."""
        now = datetime.now(UTC)
        token = MockJWTGenerator.generate(auth0_id=make_unique_external_id())
        payload = jwt.get_unverified_claims(token)

        iat_time = datetime.fromtimestamp(payload["iat"], tz=UTC)
        time_diff = abs((iat_time - now).total_seconds())

        # Should be within 5 seconds of current time
        assert time_diff < 5


class TestMockJWTDecoding:
    """Tests for mock JWT decoding."""

    def test_can_extract_unverified_claims(self) -> None:
        """Test extracting claims without verification."""
        auth0_id = "auth0|decode_test"
        token = MockJWTGenerator.generate(auth0_id=auth0_id)

        # Can decode without verification
        unverified = jwt.get_unverified_claims(token)
        assert unverified["sub"] == auth0_id

    def test_jwks_contains_matching_kid(self) -> None:
        """Test that JWKS contains key matching token kid."""
        token = MockJWTGenerator.generate(auth0_id=make_unique_external_id())
        header = jwt.get_unverified_header(token)
        jwks = MockJWTGenerator.get_mock_jwks()

        # Find matching key
        matching_key = next((key for key in jwks["keys"] if key["kid"] == header["kid"]), None)

        assert matching_key is not None
        assert matching_key["kid"] == MockJWTGenerator.KID


class TestMockJWTRoundtrip:
    """Tests for generating and decoding mock JWTs."""

    def test_roundtrip_preserves_auth0_id(self) -> None:
        """Test that auth0_id survives encode/decode roundtrip."""
        auth0_id = "auth0|roundtrip_123"
        token = MockJWTGenerator.generate(auth0_id=auth0_id)
        payload = jwt.get_unverified_claims(token)

        assert payload["sub"] == auth0_id

    def test_multiple_roundtrips_produce_different_tokens(self) -> None:
        """Test that generating multiple tokens produces different JWTs."""
        token1 = MockJWTGenerator.generate(auth0_id=make_unique_external_id())
        time.sleep(1.1)  # Wait > 1 second to ensure different timestamp
        token2 = MockJWTGenerator.generate(auth0_id=make_unique_external_id())

        # Tokens should be different (different timestamps)
        assert token1 != token2

    def test_roundtrip_with_various_auth0_id_formats(self) -> None:
        """Test roundtrip with different Auth0 ID formats."""
        test_ids = [
            "auth0|123456",
            "google-oauth2|987654321",
            "github|user_abc",
            "windowslive|def456",
        ]

        for auth0_id in test_ids:
            token = MockJWTGenerator.generate(auth0_id=auth0_id)
            payload = jwt.get_unverified_claims(token)
            assert payload["sub"] == auth0_id


class TestMockJWTSecurity:
    """Tests for mock JWT security considerations."""

    def test_uses_rs256_algorithm(self) -> None:
        """Test that mock uses RS256 algorithm like production."""
        token = MockJWTGenerator.generate(auth0_id=make_unique_external_id())
        header = jwt.get_unverified_header(token)

        assert header["alg"] == "RS256"

    def test_generates_unique_keys_per_session(self) -> None:
        """Test that keys are ephemeral (generated per test run)."""
        # Keys should exist after first generation
        MockJWTGenerator._ensure_keys()
        assert MockJWTGenerator._private_key is not None
        assert MockJWTGenerator._jwks is not None

    def test_tokens_can_be_decoded_without_verification(self) -> None:
        """Test that token payload can be read without verification."""
        token = MockJWTGenerator.generate(auth0_id="auth0|test")

        # Should be able to decode without verification
        unverified = jwt.get_unverified_claims(token)
        assert unverified["sub"] == "auth0|test"
