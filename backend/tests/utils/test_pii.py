"""Tests for PII hashing utilities."""

from unittest.mock import patch

import pytest
from app.utils.pii import hash_pii

# note: hash result is an opaque 64-character hex string (HMAC-SHA256)


def test_hash_pii_deterministic() -> None:
    """Test that hash_pii produces consistent output for same input."""
    email = "test@example.com"
    hash1 = hash_pii(email)
    hash2 = hash_pii(email)

    assert hash1 == hash2, "Same input should produce same hash"


def test_hash_pii_length() -> None:
    """Test that hash_pii returns exactly 64 characters."""
    email = "user@example.com"
    phone = "+447700900123"

    assert len(hash_pii(email)) == 64
    assert len(hash_pii(phone)) == 64


def test_hash_pii_different_inputs() -> None:
    """Test that different inputs produce different hashes."""
    email1 = "user1@example.com"
    email2 = "user2@example.com"

    hash1 = hash_pii(email1)
    hash2 = hash_pii(email2)

    assert hash1 != hash2, "Different inputs should produce different hashes"


def test_hash_pii_empty_string() -> None:
    """Test that hash_pii handles empty string."""
    result = hash_pii("")
    assert len(result) == 64


def test_hash_pii_unicode() -> None:
    """Test that hash_pii handles Unicode characters."""
    unicode_email = "user@例え.jp"  # Japanese domain
    result = hash_pii(unicode_email)
    assert len(result) == 64


def test_hash_pii_case_sensitivity() -> None:
    """Test that hash_pii behavior for different input case is explicit and locked in."""
    lower = "user@example.com"
    mixed = "User@Example.com"

    lower_hash = hash_pii(lower)
    mixed_hash = hash_pii(mixed)

    # Document current behavior: case differences SHOULD produce different hashes.
    # If behavior changes in the future (e.g. normalization added), this test
    # should be updated to reflect that new, intentional behavior.
    assert lower_hash != mixed_hash
    assert len(lower_hash) == 64
    assert len(mixed_hash) == 64


def test_hash_pii_whitespace_sensitivity() -> None:
    """Test that hash_pii behavior for leading/trailing whitespace is explicit and locked in."""
    base = "user@example.com"
    padded = "  user@example.com  "

    base_hash = hash_pii(base)
    padded_hash = hash_pii(padded)

    # Document current behavior: leading/trailing whitespace SHOULD produce different hashes.
    # If hash_pii is later changed to normalize/strip inputs, this test should
    # be updated accordingly to match that intentional behavior.
    assert base_hash != padded_hash
    assert len(base_hash) == 64
    assert len(padded_hash) == 64


def test_hash_pii_raises_on_empty_secret() -> None:
    """Test that hash_pii raises ValueError when PII_HASH_SECRET is empty."""
    with patch("app.utils.pii.settings") as mock_settings:
        mock_settings.PII_HASH_SECRET = ""
        with pytest.raises(ValueError, match="PII_HASH_SECRET must be configured and non-empty"):
            hash_pii("test@example.com")


def test_hash_pii_raises_on_none_secret() -> None:
    """Test that hash_pii raises ValueError when PII_HASH_SECRET is None."""
    with patch("app.utils.pii.settings") as mock_settings:
        mock_settings.PII_HASH_SECRET = None
        with pytest.raises(ValueError, match="PII_HASH_SECRET must be configured and non-empty"):
            hash_pii("test@example.com")


def test_hash_pii_raises_on_placeholder_secret() -> None:
    """Test that hash_pii raises ValueError when PII_HASH_SECRET is the placeholder value."""
    with patch("app.utils.pii.settings") as mock_settings:
        mock_settings.PII_HASH_SECRET = "REPLACE_ME_WITH_RANDOM_SECRET"
        with pytest.raises(ValueError, match="PII_HASH_SECRET is set to placeholder value"):
            hash_pii("test@example.com")
