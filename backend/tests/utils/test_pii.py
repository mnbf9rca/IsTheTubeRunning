"""Tests for PII hashing utilities."""

from app.utils.pii import hash_pii

# note: hash result is an opaque 12-character hex string


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


def test_hash_pii_examples_from_docstring() -> None:
    """Test the examples from the docstring."""
    # Note: These are the actual hashes, verifying they match
    assert hash_pii("user@example.com") == "b4c9a289323b21a01c3e940f150eb9b8c542587f1abfd8f0e1cc1ffc5e475514"
    assert hash_pii("+447700900123") == "a8acc3a90a7b4e4dc65e93db9240ed26523050ef754d63b75b5161de76781436"
