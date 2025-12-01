"""Tests for User model and related models (EmailAddress, PhoneNumber)."""

import uuid

from app.models.user import EmailAddress, PhoneNumber
from app.utils.pii import hash_pii


def test_email_address_auto_generates_contact_hash() -> None:
    """Test that EmailAddress automatically generates contact_hash from email."""
    email = "test@example.com"
    user_id = uuid.uuid4()

    # Create EmailAddress with only email provided (no contact_hash)
    email_address = EmailAddress(user_id=user_id, email=email)

    # Verify hash was auto-generated
    assert email_address.contact_hash == hash_pii(email)
    assert len(email_address.contact_hash) == 64


def test_email_address_preserves_explicit_contact_hash() -> None:
    """Test that EmailAddress preserves explicitly provided contact_hash."""
    email = "test@example.com"
    user_id = uuid.uuid4()
    explicit_hash = "explicit_hash_value_0123456789abcdef0123456789abcdef01234567"

    # Create EmailAddress with explicit contact_hash
    email_address = EmailAddress(user_id=user_id, email=email, contact_hash=explicit_hash)

    # Verify the explicit hash was preserved (not overwritten)
    assert email_address.contact_hash == explicit_hash
    assert email_address.contact_hash != hash_pii(email)


def test_phone_number_auto_generates_contact_hash() -> None:
    """Test that PhoneNumber automatically generates contact_hash from phone."""
    phone = "+447700900123"
    user_id = uuid.uuid4()

    # Create PhoneNumber with only phone provided (no contact_hash)
    phone_number = PhoneNumber(user_id=user_id, phone=phone)

    # Verify hash was auto-generated
    assert phone_number.contact_hash == hash_pii(phone)
    assert len(phone_number.contact_hash) == 64


def test_phone_number_preserves_explicit_contact_hash() -> None:
    """Test that PhoneNumber preserves explicitly provided contact_hash."""
    phone = "+447700900123"
    user_id = uuid.uuid4()
    explicit_hash = "explicit_hash_value_0123456789abcdef0123456789abcdef01234567"

    # Create PhoneNumber with explicit contact_hash
    phone_number = PhoneNumber(user_id=user_id, phone=phone, contact_hash=explicit_hash)

    # Verify the explicit hash was preserved (not overwritten)
    assert phone_number.contact_hash == explicit_hash
    assert phone_number.contact_hash != hash_pii(phone)
