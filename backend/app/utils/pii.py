"""PII (Personally Identifiable Information) utilities for safe logging."""

import hashlib


def hash_pii(value: str) -> str:
    """
    Hash PII value for safe logging and tracing.

    This is a pure function - same input always produces same output.
    Uses SHA256 and returns the first 12 characters of the hex digest.

    The hash is used in logs and OpenTelemetry spans to protect user privacy
    while maintaining debuggability. The 12-character hash provides sufficient
    uniqueness for correlation without storing full PII in logs/traces.

    Examples:
        >>> hash_pii("user@example.com")
        'b4c9a289323b'
        >>> hash_pii("+447700900123")
        'a8acc3a90a7b'

    Args:
        value: Email address or phone number to hash

    Returns:
        12-character lowercase hexadecimal hash (first 12 chars of SHA256)
    """
    return hashlib.sha256(value.encode()).hexdigest()[:12]
