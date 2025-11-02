"""Authentication service for user management."""

from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class AuthService:
    """Service for authentication and user management."""

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize auth service.

        Args:
            db: Database session
        """
        self.db = db

    async def get_user_by_external_id(self, external_id: str, auth_provider: str = "auth0") -> User | None:
        """
        Get user by external ID and auth provider.

        Args:
            external_id: External user identifier from auth provider (e.g., 'auth0|123abc')
            auth_provider: Authentication provider name (default: 'auth0')

        Returns:
            User instance if found, None otherwise
        """
        result = await self.db.execute(
            select(User).where(and_(User.external_id == external_id, User.auth_provider == auth_provider))
        )
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        """
        Get user by internal UUID.

        Args:
            user_id: Internal user UUID

        Returns:
            User instance if found, None otherwise
        """
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create_user(self, external_id: str, auth_provider: str = "auth0") -> User:
        """
        Create a new user.

        Args:
            external_id: External user identifier from auth provider
            auth_provider: Authentication provider name (default: 'auth0')

        Returns:
            Newly created User instance

        Raises:
            IntegrityError: If user with external_id + auth_provider already exists
        """
        user = User(external_id=external_id, auth_provider=auth_provider)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def get_or_create_user(self, external_id: str, auth_provider: str = "auth0") -> User:
        """
        Get existing user or create new one if doesn't exist.

        This is the primary method used during authentication.
        On first login, a new user record is automatically created.

        Args:
            external_id: External user identifier from auth provider
            auth_provider: Authentication provider name (default: 'auth0')

        Returns:
            User instance (existing or newly created)
        """
        # Try to get existing user
        user = await self.get_user_by_external_id(external_id, auth_provider)

        # Create new user if doesn't exist
        if user is None:
            user = await self.create_user(external_id, auth_provider)

        return user
