"""Extract database credentials from DATABASE_URL for use in shell scripts.

This utility decrypts .env.vault using DOTENV_KEY and parses DATABASE_URL
to extract individual connection parameters (user, password, host, port, database).

Usage:
    # Get all credentials as export statements (for eval in bash)
    uv run python -m app.utils.extract_db_credentials export

    # Get individual credential field
    uv run python -m app.utils.extract_db_credentials password
    uv run python -m app.utils.extract_db_credentials user
    uv run python -m app.utils.extract_db_credentials host
    uv run python -m app.utils.extract_db_credentials port
    uv run python -m app.utils.extract_db_credentials database

Example bash usage:
    # Extract all credentials
    eval $(uv run python -m app.utils.extract_db_credentials export)
    echo "Connecting to $PGHOST as $PGUSER"

    # Extract single value
    DB_PASSWORD=$(uv run python -m app.utils.extract_db_credentials password)
"""

import os
import sys
from urllib.parse import urlparse

from dotenv_vault import load_dotenv


def extract_credentials(database_url: str, mode: str = "password") -> str:
    """Extract database credentials from DATABASE_URL.

    Args:
        database_url: PostgreSQL connection URL (e.g., postgresql+asyncpg://user:pass@host:5432/db)
        mode: Extraction mode - "export", "user", "password", "host", "port", or "database"

    Returns:
        Extracted credential(s) as string. For "export" mode, returns multi-line bash export statements.
        For single field modes, returns just the value.

    Raises:
        ValueError: If database_url is empty or mode is invalid
    """
    if not database_url:
        msg = "DATABASE_URL cannot be empty"
        raise ValueError(msg)

    # Parse the URL
    # Example: postgresql+asyncpg://postgres:password@localhost:5432/isthetube
    parsed = urlparse(database_url)

    # Output based on mode
    if mode == "export":
        # Export format for eval in bash
        lines = [
            f"export PGUSER='{parsed.username or ''}'",
            f"export PGPASSWORD='{parsed.password or ''}'",
            f"export PGHOST='{parsed.hostname or ''}'",
            f"export PGPORT='{parsed.port or 5432}'",
            f"export PGDATABASE='{parsed.path.lstrip('/') or ''}'",
        ]
        return "\n".join(lines)
    if mode in ["user", "password", "host", "port", "database"]:
        # Single value extraction
        values = {
            "user": parsed.username or "",
            "password": parsed.password or "",
            "host": parsed.hostname or "",
            "port": str(parsed.port or 5432),
            "database": parsed.path.lstrip("/") or "",
        }
        return values[mode]
    msg = f"Unknown mode '{mode}'. Use: export, user, password, host, port, database"
    raise ValueError(msg)


def get_mode_from_args(args: list[str]) -> str:
    """Parse command line arguments to determine extraction mode.

    Pure function that returns the mode based on command line arguments.

    Args:
        args: Command line arguments (typically sys.argv)

    Returns:
        Extraction mode string ("export", "user", "password", etc.)
    """
    if len(args) > 1:
        return args[1]
    return "password"  # Default to password for backwards compatibility


def load_database_url() -> str:
    """Load DATABASE_URL from environment, optionally decrypting vault.

    Loads environment variables from .env.vault using DOTENV_KEY if DATABASE_URL
    is not already set in the environment.

    Returns:
        DATABASE_URL value

    Raises:
        ValueError: If DATABASE_URL is not found or empty
    """
    # Load environment variables from .env.vault using DOTENV_KEY
    # (Only if DATABASE_URL is not already set - allows testing without vault)
    if "DATABASE_URL" not in os.environ:
        load_dotenv()

    database_url = os.getenv("DATABASE_URL", "")

    if not database_url:
        msg = "DATABASE_URL not found in environment"
        raise ValueError(msg)

    return database_url


def main() -> None:
    """CLI entry point.

    Orchestrates the credential extraction process:
    1. Loads DATABASE_URL from environment (or .env.vault)
    2. Determines extraction mode from command line arguments
    3. Extracts and prints credentials
    4. Handles errors and exits with appropriate status codes
    """
    try:
        database_url = load_database_url()
        mode = get_mode_from_args(sys.argv)
        result = extract_credentials(database_url, mode)
        print(result)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
