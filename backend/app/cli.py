#!/usr/bin/env python3
"""CLI tool for admin user management.

This module provides command-line tools for creating and managing admin users
in local development environments. It eliminates the need for manual SQL commands
and provides a convenient interface for common admin operations.

Usage:
    # Create an admin user (most common use case)
    uv run python -m app.cli create-admin

    # Create a regular user
    uv run python -m app.cli create-user

    # Grant admin privileges to existing user
    uv run python -m app.cli grant-admin <user-id>

    # List all admin users
    uv run python -m app.cli list-admins

    # List all users
    uv run python -m app.cli list-users

    # Revoke admin privileges
    uv run python -m app.cli revoke-admin <user-id>
"""

import argparse
import asyncio
import sys
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session_factory
from app.models.admin import AdminRole
from app.utils.admin_helpers import (
    create_admin_user,
    create_user,
    find_user_by_external_id,
    get_user_by_id,
    grant_admin,
    list_admin_users,
    list_users,
    revoke_admin,
)


async def cmd_create_admin(args: argparse.Namespace, session: AsyncSession) -> int:
    """
    Create a new admin user.

    Args:
        args: Parsed command-line arguments
        session: Database session

    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        external_id = args.external_id or None
        role = AdminRole.SUPERADMIN if args.superadmin else AdminRole.ADMIN

        user, admin = await create_admin_user(session, external_id=external_id, role=role)

        print("✅ Created admin user successfully!")
        print(f"   User ID:     {user.id}")
        print(f"   External ID: {user.external_id}")
        print(f"   Provider:    {user.auth_provider}")
        print(f"   Role:        {admin.role.value}")
        print(f"   Granted at:  {admin.granted_at}")
        print()
        print("💡 Save the User ID to use with other CLI commands")
        return 0
    except ValueError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1


async def cmd_create_user(args: argparse.Namespace, session: AsyncSession) -> int:
    """
    Create a new regular user.

    Args:
        args: Parsed command-line arguments
        session: Database session

    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        external_id = args.external_id or None

        user = await create_user(session, external_id=external_id)

        print("✅ Created user successfully!")
        print(f"   User ID:     {user.id}")
        print(f"   External ID: {user.external_id}")
        print(f"   Provider:    {user.auth_provider}")
        print(f"   Created at:  {user.created_at}")
        print()
        print("💡 Use 'grant-admin {user_id}' to make this user an admin")
        return 0
    except ValueError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1


async def cmd_grant_admin(args: argparse.Namespace, session: AsyncSession) -> int:
    """
    Grant admin privileges to an existing user.

    Args:
        args: Parsed command-line arguments
        session: Database session

    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        # Parse user identifier
        if args.external_id:
            user = await find_user_by_external_id(session, args.identifier, auth_provider=args.provider)
            if not user:
                print(
                    f"❌ Error: User with external_id '{args.identifier}' not found (provider: {args.provider})",
                    file=sys.stderr,
                )
                return 1
            user_id = user.id
        else:
            try:
                user_id = uuid.UUID(args.identifier)
            except ValueError:
                print(
                    f"❌ Error: Invalid UUID '{args.identifier}'. Use --external-id flag if providing an external ID",
                    file=sys.stderr,
                )
                return 1

        # Grant admin
        role = AdminRole.SUPERADMIN if args.superadmin else AdminRole.ADMIN
        admin = await grant_admin(session, user_id=user_id, role=role)

        # Get user details for display
        user = await get_user_by_id(session, user_id)

        print("✅ Granted admin privileges successfully!")
        print(f"   User ID:     {user_id}")
        if user:
            print(f"   External ID: {user.external_id}")
            print(f"   Provider:    {user.auth_provider}")
        print(f"   Role:        {admin.role.value}")
        print(f"   Granted at:  {admin.granted_at}")
        return 0
    except ValueError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1


async def cmd_revoke_admin(args: argparse.Namespace, session: AsyncSession) -> int:
    """
    Revoke admin privileges from a user.

    Args:
        args: Parsed command-line arguments
        session: Database session

    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        # Parse user identifier
        if args.external_id:
            user = await find_user_by_external_id(session, args.identifier, auth_provider=args.provider)
            if not user:
                print(
                    f"❌ Error: User with external_id '{args.identifier}' not found (provider: {args.provider})",
                    file=sys.stderr,
                )
                return 1
            user_id = user.id
        else:
            try:
                user_id = uuid.UUID(args.identifier)
            except ValueError:
                print(
                    f"❌ Error: Invalid UUID '{args.identifier}'. Use --external-id flag if providing an external ID",
                    file=sys.stderr,
                )
                return 1

        # Revoke admin
        was_revoked = await revoke_admin(session, user_id=user_id)

        if was_revoked:
            print(f"✅ Revoked admin privileges from user {user_id}")
            return 0
        print(
            f"Info: User {user_id} was not an admin (no action taken)",
            file=sys.stderr,
        )
        return 0
    except ValueError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1


async def cmd_list_admins(args: argparse.Namespace, session: AsyncSession) -> int:
    """
    List all admin users.

    Args:
        args: Parsed command-line arguments
        session: Database session

    Returns:
        Exit code (0 for success, 1 for error)
    """
    admins = await list_admin_users(session)

    if not admins:
        print("No admin users found")
        return 0

    print(f"Found {len(admins)} admin user(s):\n")
    print(f"{'User ID':<38} {'External ID':<30} {'Role':<12} Granted At")
    print("-" * 110)

    for user, admin in admins:
        granted_at_str = admin.granted_at.strftime("%Y-%m-%d %H:%M:%S")
        print(f"{user.id!s:<38} {user.external_id:<30} {admin.role.value:<12} {granted_at_str}")

    return 0


async def cmd_list_users(args: argparse.Namespace, session: AsyncSession) -> int:
    """
    List all users with pagination.

    Args:
        args: Parsed command-line arguments
        session: Database session

    Returns:
        Exit code (0 for success, 1 for error)
    """
    users = await list_users(session, limit=args.limit, offset=args.offset)

    if not users:
        print("No users found")
        return 0

    print(f"Showing {len(users)} user(s) (limit: {args.limit}, offset: {args.offset}):\n")
    print(f"{'User ID':<38} {'External ID':<30} {'Provider':<12} Created At")
    print("-" * 110)

    for user in users:
        created_at_str = user.created_at.strftime("%Y-%m-%d %H:%M:%S")
        print(f"{user.id!s:<38} {user.external_id:<30} {user.auth_provider:<12} {created_at_str}")

    print("\n💡 Use --limit and --offset to paginate results (e.g., --limit 50 --offset 50 for next page)")
    return 0


def main() -> int:
    """
    Main entry point for the CLI tool.

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    parser = argparse.ArgumentParser(
        description="Admin user management CLI tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create an admin user (most common)
  uv run python -m app.cli create-admin

  # Create an admin user with custom external ID
  uv run python -m app.cli create-admin --external-id "auth0|abc123"

  # Create a regular user
  uv run python -m app.cli create-user

  # Grant admin to existing user by UUID
  uv run python -m app.cli grant-admin 550e8400-e29b-41d4-a716-446655440000

  # Grant admin to existing user by external ID
  uv run python -m app.cli grant-admin auth0|abc123 --external-id

  # List all admin users
  uv run python -m app.cli list-admins

  # List users
  uv run python -m app.cli list-users --limit 20

  # Revoke admin privileges
  uv run python -m app.cli revoke-admin 550e8400-e29b-41d4-a716-446655440000
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # create-admin command
    create_admin_parser = subparsers.add_parser(
        "create-admin",
        help="Create a new admin user (user + admin privileges)",
        description="Create a new user and immediately grant admin privileges. "
        "This is the most common command for local development.",
    )
    create_admin_parser.add_argument(
        "--external-id",
        type=str,
        help="Custom external ID (e.g., 'auth0|abc123'). If not provided, generates 'cli|<random>'",
    )
    create_admin_parser.add_argument(
        "--superadmin",
        action="store_true",
        help="Grant superadmin role instead of regular admin",
    )

    # create-user command
    create_user_parser = subparsers.add_parser(
        "create-user",
        help="Create a new regular user (no admin privileges)",
        description="Create a new user without admin privileges. Use 'grant-admin' to promote later.",
    )
    create_user_parser.add_argument(
        "--external-id",
        type=str,
        help="Custom external ID (e.g., 'auth0|abc123'). If not provided, generates 'cli|<random>'",
    )

    # grant-admin command
    grant_admin_parser = subparsers.add_parser(
        "grant-admin",
        help="Grant admin privileges to an existing user",
        description="Grant admin privileges to an existing user by UUID or external ID.",
    )
    grant_admin_parser.add_argument(
        "identifier",
        type=str,
        help="User UUID or external ID (use --external-id flag if providing external ID)",
    )
    grant_admin_parser.add_argument(
        "--external-id",
        action="store_true",
        help="Treat identifier as external ID instead of UUID",
    )
    grant_admin_parser.add_argument(
        "--provider",
        type=str,
        default="auth0",
        help="Auth provider (default: auth0). Only used with --external-id",
    )
    grant_admin_parser.add_argument(
        "--superadmin",
        action="store_true",
        help="Grant superadmin role instead of regular admin",
    )

    # revoke-admin command
    revoke_admin_parser = subparsers.add_parser(
        "revoke-admin",
        help="Revoke admin privileges from a user",
        description="Remove admin privileges from an existing admin user.",
    )
    revoke_admin_parser.add_argument(
        "identifier",
        type=str,
        help="User UUID or external ID (use --external-id flag if providing external ID)",
    )
    revoke_admin_parser.add_argument(
        "--external-id",
        action="store_true",
        help="Treat identifier as external ID instead of UUID",
    )
    revoke_admin_parser.add_argument(
        "--provider",
        type=str,
        default="auth0",
        help="Auth provider (default: auth0). Only used with --external-id",
    )

    # list-admins command
    subparsers.add_parser(
        "list-admins",
        help="List all admin users",
        description="Display a list of all users with admin privileges.",
    )

    # list-users command
    list_users_parser = subparsers.add_parser(
        "list-users",
        help="List all users with pagination",
        description="Display a paginated list of all users in the system.",
    )
    list_users_parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of users to display (default: 50)",
    )
    list_users_parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Number of users to skip (default: 0)",
    )

    # Parse arguments
    args = parser.parse_args()

    # Show help if no command provided
    if not args.command:
        parser.print_help()
        return 1

    # Dispatch to command handler
    command_handlers = {
        "create-admin": cmd_create_admin,
        "create-user": cmd_create_user,
        "grant-admin": cmd_grant_admin,
        "revoke-admin": cmd_revoke_admin,
        "list-admins": cmd_list_admins,
        "list-users": cmd_list_users,
    }

    if handler := command_handlers.get(args.command):
        # Create async wrapper to handle session creation for production use
        async def run_with_session() -> int:
            async with get_session_factory()() as session:
                try:
                    return await handler(args, session)
                except Exception as e:
                    print(f"❌ Unexpected error: {e}", file=sys.stderr)
                    return 1

        return asyncio.run(run_with_session())

    print(f"❌ Unknown command: {args.command}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
