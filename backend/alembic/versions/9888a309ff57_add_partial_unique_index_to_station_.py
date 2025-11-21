"""add_partial_unique_index_to_station_connections

Revision ID: 9888a309ff57
Revises: 7df10ab411af
Create Date: 2025-11-21 10:38:01.489060

Fix for Issue #230: Replace standard unique constraint with partial unique index
to enable atomic soft delete operations without flush().

The partial unique index only applies WHERE deleted_at IS NULL, allowing:
- Soft delete (UPDATE) and INSERT operations in same transaction
- Atomic commit without intermediate flush()
- Zero downtime during network graph rebuilds

"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "9888a309ff57"
down_revision: str | Sequence[str] | None = "7df10ab411af"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    Replace standard unique constraint with partial unique index on station_connections.
    This allows soft-deleted records to accumulate while maintaining uniqueness for
    active records only.
    """
    # Drop the existing unique constraint
    op.drop_constraint("uq_station_connection", "station_connections", type_="unique")

    # Create partial unique index (only applies WHERE deleted_at IS NULL)
    # This allows multiple soft-deleted records with same (from, to, line)
    # but enforces uniqueness for active records
    op.create_index(
        "uq_station_connection_active",
        "station_connections",
        ["from_station_id", "to_station_id", "line_id"],
        unique=True,
        postgresql_where=text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    """Downgrade schema.

    Restore original unique constraint. Note: This will fail if there are
    multiple soft-deleted records with the same (from, to, line) combination.
    """
    # Drop the partial unique index
    op.drop_index("uq_station_connection_active", table_name="station_connections")

    # Recreate the original unique constraint
    # WARNING: This will fail if soft-deleted duplicates exist
    op.create_unique_constraint(
        "uq_station_connection",
        "station_connections",
        ["from_station_id", "to_station_id", "line_id"],
    )
