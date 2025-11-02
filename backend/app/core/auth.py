"""Authentication and authorization utilities."""

from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlunparse

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import require_config, settings
from app.core.database import get_db
from app.models.user import User

# Validate required auth configuration on module load
require_config("AUTH0_DOMAIN", "AUTH0_API_AUDIENCE", "AUTH0_ALGORITHMS")

# Mock JWKS cache for DEBUG mode (populated by tests)
_mock_jwks: dict[str, Any] | None = None


def set_mock_jwks(jwks: dict[str, Any]) -> None:
    """
    Set mock JWKS for DEBUG mode testing.

    This should only be called by test fixtures in DEBUG mode.

    Args:
        jwks: JWKS dictionary with test public keys

    Raises:
        RuntimeError: If called when DEBUG=False
    """
    if not settings.DEBUG:
        msg = "set_mock_jwks() can only be called in DEBUG mode"
        raise RuntimeError(msg)
    global _mock_jwks  # noqa: PLW0603
    _mock_jwks = jwks


# HTTP Bearer security scheme for JWT tokens
security = HTTPBearer()

# JWKS cache (JSON Web Key Set from Auth0)
_jwks_cache: dict[str, Any] | None = None
_jwks_cache_time: datetime | None = None
_jwks_cache_ttl = timedelta(hours=1)


async def get_jwks(domain: str) -> dict[str, Any]:
    """
    Fetch JWKS (JSON Web Key Set) from Auth0.

    This is used to verify JWT signatures. Results are cached for 1 hour.

    Args:
        domain: Auth0 domain (e.g., 'your-tenant.auth0.com')

    Returns:
        JWKS dictionary containing public keys

    Raises:
        HTTPException: If JWKS cannot be fetched
    """
    global _jwks_cache, _jwks_cache_time  # noqa: PLW0603

    # Return cached JWKS if still valid and contains keys
    now = datetime.now(UTC)
    if (
        _jwks_cache is not None
        and "keys" in _jwks_cache
        and _jwks_cache_time is not None
        and now - _jwks_cache_time < _jwks_cache_ttl
    ):
        return _jwks_cache

    # Fetch fresh JWKS from Auth0
    try:
        async with httpx.AsyncClient() as client:
            jwks_url = urlunparse(("https", domain, "/.well-known/jwks.json", "", "", ""))
            response = await client.get(jwks_url, timeout=10.0)
            response.raise_for_status()
            _jwks_cache = response.json()
            _jwks_cache_time = now
            return _jwks_cache
    except (httpx.HTTPError, httpx.TimeoutException) as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to fetch JWKS from Auth0: {e!s}",
        ) from e


async def verify_jwt(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict[str, Any]:
    """
    Verify JWT token from Auth0 or mock JWT in debug mode.

    Args:
        credentials: HTTP Bearer credentials containing JWT token

    Returns:
        JWT payload dictionary containing claims (e.g., 'sub', 'iat', 'exp')

    Raises:
        HTTPException: If token is invalid or verification fails
    """
    token = credentials.credentials

    try:
        # Decode JWT header to get key ID (kid)
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        if not kid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing 'kid' in header",
            )

        # Fetch JWKS (use mock JWKS in DEBUG mode)
        if settings.DEBUG and _mock_jwks is not None:
            jwks = _mock_jwks
        elif settings.DEBUG:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Mock JWKS not configured for DEBUG mode",
            )
        else:
            jwks = await get_jwks(settings.AUTH0_DOMAIN)

        # Find matching key
        matching_key = next((key for key in jwks.get("keys", []) if key.get("kid") == kid), None)

        if not matching_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to find appropriate signing key",
            )

        # Validate required JWKS fields are present
        required_fields = ["kty", "kid", "use", "n", "e"]
        missing_fields = [field for field in required_fields if field not in matching_key]
        if missing_fields:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"JWKS key is missing required fields: {', '.join(missing_fields)}",
            )

        # Extract RSA key components
        rsa_key = {
            "kty": matching_key["kty"],
            "kid": matching_key["kid"],
            "use": matching_key["use"],
            "n": matching_key["n"],
            "e": matching_key["e"],
        }

        # Verify and decode JWT
        issuer = urlunparse(("https", settings.AUTH0_DOMAIN, "/", "", "", ""))
        return jwt.decode(
            token,
            rsa_key,
            algorithms=settings.AUTH0_ALGORITHMS,
            audience=settings.AUTH0_API_AUDIENCE,
            issuer=issuer,
        )

    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication credentials: {e!s}",
        ) from e


async def get_current_user(
    payload: dict[str, Any] = Depends(verify_jwt),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Get current user from database, auto-create if doesn't exist.

    This dependency extracts the Auth0 user ID from the JWT payload,
    looks up the user in the database, and creates a new user record
    if this is their first authenticated request.

    Args:
        payload: JWT payload from verify_jwt dependency
        db: Database session

    Returns:
        User model instance

    Raises:
        HTTPException: If token missing 'sub' claim or database error
    """
    # Import here to avoid circular dependency
    from app.services.auth_service import AuthService  # noqa: PLC0415

    external_id = payload.get("sub")
    if not external_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing 'sub' claim",
        )

    auth_service = AuthService(db)
    return await auth_service.get_or_create_user(external_id, auth_provider="auth0")
