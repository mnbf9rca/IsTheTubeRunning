"""remove_color_from_lines

Revision ID: 595219043932
Revises: 90d1c387ce78
Create Date: 2025-11-10 13:13:37.821925

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "595219043932"
down_revision: str | Sequence[str] | None = "90d1c387ce78"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Remove color column from lines table
    # Line colors are a frontend presentation concern and are maintained in frontend/src/lib/tfl-colors.ts
    op.drop_column("lines", "color")


def downgrade() -> None:
    """Downgrade schema."""
    # Restore color column with default value #000000 (black placeholder)
    op.add_column(
        "lines",
        sa.Column("color", sa.String(length=7), nullable=False, server_default="#000000"),
    )
