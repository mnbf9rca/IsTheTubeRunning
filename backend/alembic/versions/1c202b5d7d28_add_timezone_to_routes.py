"""add_timezone_to_routes

Revision ID: 1c202b5d7d28
Revises: e9121fedff17
Create Date: 2025-11-04 09:17:38.900697

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1c202b5d7d28"
down_revision: str | Sequence[str] | None = "e9121fedff17"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add timezone column to routes table
    op.add_column(
        "routes",
        sa.Column(
            "timezone",
            sa.String(length=64),
            nullable=False,
            server_default="Europe/London",
            comment="IANA timezone for schedule interpretation (e.g., Europe/London). Schedule times are naive and interpreted in this timezone.",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove timezone column
    op.drop_column("routes", "timezone")
