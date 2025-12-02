"""Extract database credentials from SECRET_DATABASE_URL and environment variables for use in shell scripts.

This utility extracts database connection parameters and environment variables.
Environment variables must be available (injected via `dotenvx run --` wrapper).

Usage:
    # Get all credentials as export statements (for eval in bash)
    dotenvx run -- uv run python -m app.utils.extract_db_credentials export

    # Get individual credential field from SECRET_DATABASE_URL
    dotenvx run -- uv run python -m app.utils.extract_db_credentials password
    dotenvx run -- uv run python -m app.utils.extract_db_credentials user
    dotenvx run -- uv run python -m app.utils.extract_db_credentials host
    dotenvx run -- uv run python -m app.utils.extract_db_credentials port
    dotenvx run -- uv run python -m app.utils.extract_db_credentials database

    # Extract environment variable directly
    dotenvx run -- uv run python -m app.utils.extract_db_credentials tunnel_token

Example bash usage:
    # Extract all credentials
    eval $(dotenvx run -- uv run python -m app.utils.extract_db_credentials export)
    echo "Connecting to $PGHOST as $PGUSER"

    # Extract single value
    DB_PASSWORD=$(dotenvx run -- uv run python -m app.utils.extract_db_credentials password)

    # For simple values, use dotenvx get directly:
    TUNNEL_TOKEN=$(dotenvx get CLOUDFLARE_TUNNEL_TOKEN)
"""

import os
import shlex
import sys
from urllib.parse import urlparse


def extract_credentials(database_url: str, mode: str = "password") -> str:
    """Extract database credentials from SECRET_DATABASE_URL.

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
        msg = "SECRET_DATABASE_URL cannot be empty"
        raise ValueError(msg)

    # Parse the URL
    # Example: postgresql+asyncpg://postgres:password@localhost:5432/isthetube
    parsed = urlparse(database_url)

    # Output based on mode
    if mode == "export":
        # Export format for eval in bash, safely shell-escaped
        lines = [
            f"export PGUSER={shlex.quote(parsed.username or '')}",
            f"export PGPASSWORD={shlex.quote(parsed.password or '')}",
            f"export PGHOST={shlex.quote(parsed.hostname or '')}",
            f"export PGPORT={shlex.quote(str(parsed.port or 5432))}",
            f"export PGDATABASE={shlex.quote(parsed.path.lstrip('/') or '')}",
        ]
        return "\n".join(lines)
    if mode in {"user", "password", "host", "port", "database"}:
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

    Raises:
        ValueError: If no mode argument provided
    """
    # args[0] is script name, args[1] is the mode argument
    mode_arg_index = 1
    if len(args) <= mode_arg_index:
        msg = (
            "Mode argument required. Usage:\n"
            "  python -m app.utils.extract_db_credentials <mode>\n"
            "  Modes: export, user, password, host, port, database"
        )
        raise ValueError(msg)
    return args[mode_arg_index]


def load_database_url() -> str:
    """Load SECRET_DATABASE_URL from environment.

    Environment variables must be pre-populated (e.g., via dotenvx run wrapper).

    Returns:
        SECRET_DATABASE_URL value

    Raises:
        ValueError: If SECRET_DATABASE_URL is not found or empty
    """
    if database_url := os.getenv("SECRET_DATABASE_URL", ""):
        return database_url
    msg = "SECRET_DATABASE_URL not found in environment"
    raise ValueError(msg)


def extract_env_var(var_name: str) -> str:
    """Extract any environment variable.

    Environment variables must be pre-populated (e.g., via dotenvx run wrapper).

    Args:
        var_name: Name of environment variable to extract (e.g., "CLOUDFLARE_TUNNEL_TOKEN")

    Returns:
        Value of the environment variable

    Raises:
        ValueError: If variable not found in environment or is empty
    """
    if value := os.getenv(var_name, ""):
        return value
    msg = f"{var_name} not found in environment"
    raise ValueError(msg)


def main() -> None:
    """CLI entry point.

    Orchestrates the credential extraction process:
    1. Determines extraction mode from command line arguments
    2. For database modes: Loads DATABASE_URL and extracts credentials
    3. For environment variable modes: Extracts variable directly from .env.vault
    4. Handles errors and exits with appropriate status codes
    """
    try:
        mode = get_mode_from_args(sys.argv)

        # Special handling for tunnel_token mode - extract from environment directly
        if mode == "tunnel_token":
            result = extract_env_var("CLOUDFLARE_TUNNEL_TOKEN")
        else:
            # Database credential extraction modes
            database_url = load_database_url()
            result = extract_credentials(database_url, mode)

        print(result)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
