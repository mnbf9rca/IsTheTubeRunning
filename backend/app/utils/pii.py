"""PII (Personally Identifiable Information) utilities for safe logging."""

import hashlib
import hmac

from app.core.config import settings


def hash_pii(value: str) -> str:
    """
    Hash PII value for safe logging and tracing using HMAC-SHA256.

    This is a pure function - same input always produces same output given the
    same secret key. Uses HMAC-SHA256 to provide resistance against dictionary
    attacks on common email addresses and phone numbers.

    The hash is used in logs and OpenTelemetry spans to protect user privacy
    while maintaining debuggability. Using the full hash eliminates collision
    risk and follows cryptographic best practices.

    Examples (output depends on PII_HASH_SECRET):
        >>> # With secret="test-secret"
        >>> hash_pii("user@example.com")  # doctest: +SKIP
        '...'  # 64-character hex string
        >>> hash_pii("+447700900123")  # doctest: +SKIP
        '...'  # 64-character hex string

    Args:
        value: Email address or phone number to hash

    Returns:
        64-character lowercase hexadecimal hash (full HMAC-SHA256 digest)

    Raises:
        AttributeError: If PII_HASH_SECRET is not configured
    """
    secret = settings.PII_HASH_SECRET.encode()
    return hmac.new(secret, value.encode(), hashlib.sha256).hexdigest()
