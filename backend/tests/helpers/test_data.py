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
    Generate unique phone number for tests to prevent collisions.

    Args:
        country_code: Phone country code (default: UK)

    Returns:
        Unique phone number
    """
    # Generate a random 10-digit number for UK format
    random_digits = str(uuid.uuid4().int)[:10]
    return f"{country_code}{random_digits}"
