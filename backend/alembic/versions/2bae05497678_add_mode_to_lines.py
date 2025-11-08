"""add_mode_to_lines

Revision ID: 2bae05497678
Revises: f8838ec5262d
Create Date: 2025-11-08 10:35:51.728713

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2bae05497678"
down_revision: str | Sequence[str] | None = "f8838ec5262d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema: Add mode column to lines table."""
    # Add mode column with default value 'tube' (for existing data)
    op.add_column(
        "lines",
        sa.Column(
            "mode",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'tube'"),
        ),
    )


def downgrade() -> None:
    """Downgrade schema: Remove mode column from lines table."""
    op.drop_column("lines", "mode")
