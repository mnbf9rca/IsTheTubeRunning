"""Test data generation utilities."""

import uuid


def make_unique_external_id(prefix: str = "auth0|test") -> str:
    """
    Generate unique external_id for tests to prevent collisions.

    Args:
        prefix: Prefix for the external_id (e.g., 'auth0|test', 'google|test')

    Returns:
        Unique external_id string in format: {prefix}_{uuid}
    """
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def make_unique_email(domain: str = "example.com") -> str:
    """
    Generate unique email address for tests to prevent collisions.

    Args:
        domain: Email domain to use

    Returns:
        Unique email address
    """
    return f"test_{uuid.uuid4().hex[:8]}@{domain}"


def make_unique_phone(country_code: str = "+44") -> str:
    """
    Generate unique valid phone number for tests to prevent collisions.

    Args:
        country_code: Phone country code (default: UK +44, also supports US +1)

    Returns:
        Unique valid phone number in E.164 format
    """
    if country_code == "+44":
        # UK mobile format: +447911123XXX
        # Using a known valid base number and varying last 3 digits
        random_int = uuid.uuid4().int % 1000  # Get number between 0-999
        return f"+447911123{random_int:03d}"  # Zero-pad to 3 digits
    if country_code == "+1":
        # US format: +1 202-555-1XXX (Washington DC area code)
        random_int = uuid.uuid4().int % 1000  # Get number between 0-999
        return f"+12025551{random_int:03d}"  # Zero-pad to 3 digits
    # Generic: use provided country code + random 10 digits (may not be valid)
    random_digits = str(uuid.uuid4().int)[:10]
    return f"{country_code}{random_digits}"
