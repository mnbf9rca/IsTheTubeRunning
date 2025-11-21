"""convert_route_segment_unique_to_partial_index

Revision ID: 728def08ac79
Revises: 9888a309ff57
Create Date: 2025-11-21 21:22:20.018987

Fix for Issue #233: Replace standard unique constraint with partial unique index
to enable atomic soft delete operations without flush().

The partial unique index only applies WHERE deleted_at IS NULL, allowing:
- Soft delete (UPDATE) and INSERT operations in same transaction
- Atomic commit without intermediate flush()
- Segment sequence reuse after soft delete (e.g., upsert_segments)

"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "728def08ac79"
down_revision: str | Sequence[str] | None = "9888a309ff57"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    Replace standard unique constraint with partial unique index on user_route_segments.
    This allows soft-deleted segments to accumulate while maintaining uniqueness for
    active segments only (per route_id, sequence pair).
    """
    # Drop the existing unique constraint
    op.drop_constraint("uq_route_segment_sequence", "user_route_segments", type_="unique")

    # Create partial unique index (only applies WHERE deleted_at IS NULL)
    # This allows multiple soft-deleted segments with same (route_id, sequence)
    # but enforces uniqueness for active segments
    op.create_index(
        "uq_route_segment_sequence_active",
        "user_route_segments",
        ["route_id", "sequence"],
        unique=True,
        postgresql_where=text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    """Downgrade schema.

    Restore original unique constraint. Note: This will fail if there are
    multiple soft-deleted segments with the same (route_id, sequence) combination.
    """
    # Drop the partial unique index
    op.drop_index("uq_route_segment_sequence_active", table_name="user_route_segments")

    # Recreate the original unique constraint
    # WARNING: This will fail if soft-deleted duplicates exist
    op.create_unique_constraint(
        "uq_route_segment_sequence",
        "user_route_segments",
        ["route_id", "sequence"],
    )
