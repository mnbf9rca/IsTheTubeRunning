"""PII (Personally Identifiable Information) utilities for safe logging."""

import hashlib


def hash_pii(value: str) -> str:
    """
    Hash PII value for safe logging and tracing.

    This is a pure function - same input always produces same output.
    Uses SHA256 and returns the full 64-character hex digest.

    The hash is used in logs and OpenTelemetry spans to protect user privacy
    while maintaining debuggability. Using the full hash eliminates collision
    risk and follows cryptographic best practices.

    Examples:
        >>> hash_pii("user@example.com")
        'b4c9a289323b21a01c3e940f150eb9b8c542587f1abfd8f0e1cc1ffc5e475514'
        >>> hash_pii("+447700900123")
        'a8acc3a90a7b4e4dc65e93db9240ed26523050ef754d63b75b5161de76781436'

    Args:
        value: Email address or phone number to hash

    Returns:
        64-character lowercase hexadecimal hash (full SHA256 digest)
    """
    return hashlib.sha256(value.encode()).hexdigest()
