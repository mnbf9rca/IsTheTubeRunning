"""add route_variants_canonical to lines

Revision ID: 55ac4b0569a1
Revises: 1025d77921da
Create Date: 2025-12-11 21:07:50.233344

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "55ac4b0569a1"
down_revision: str | Sequence[str] | None = "1025d77921da"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "lines",
        sa.Column(
            "route_variants_canonical",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
            comment="Route variants with station IDs translated to canonical hub IDs (for API responses)",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("lines", "route_variants_canonical")
