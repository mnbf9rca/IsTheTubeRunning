"""add_routes_to_lines

Revision ID: 941d95fee6c2
Revises: 2bae05497678
Create Date: 2025-11-08 15:24:50.273645

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "941d95fee6c2"
down_revision: str | Sequence[str] | None = "2bae05497678"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    Add routes JSON column to lines table to store ordered route sequences
    (station lists for each route variant). This enables the frontend to show
    users only reachable stations on specific route variants.
    """
    op.add_column(
        "lines",
        sa.Column("routes", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema.

    Remove routes column from lines table.
    """
    op.drop_column("lines", "routes")
