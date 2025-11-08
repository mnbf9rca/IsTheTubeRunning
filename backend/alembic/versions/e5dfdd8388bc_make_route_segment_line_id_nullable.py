"""make_route_segment_line_id_nullable

Revision ID: e5dfdd8388bc
Revises: 941d95fee6c2
Create Date: 2025-11-08 20:26:25.006982

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5dfdd8388bc"
down_revision: str | Sequence[str] | None = "941d95fee6c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema: make route_segments.line_id nullable.

    This allows destination segments to have NULL line_id, which semantically
    means "journey terminates here" (no outgoing line to travel on).

    Note: No data migration needed - development project with no production data.
    """
    op.alter_column(
        "route_segments",
        "line_id",
        existing_type=sa.dialects.postgresql.UUID(),
        nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema: make route_segments.line_id NOT NULL again.

    Warning: This will fail if any segments have NULL line_id.
    """
    op.alter_column(
        "route_segments",
        "line_id",
        existing_type=sa.dialects.postgresql.UUID(),
        nullable=False,
    )
