"""add_line_disruption_state_logs_table

Revision ID: 8ed2312f54f3
Revises: dbef0183286a
Create Date: 2025-11-17 09:06:25.445431

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8ed2312f54f3"
down_revision: str | Sequence[str] | None = "dbef0183286a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create line_disruption_state_logs table
    op.create_table(
        "line_disruption_state_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "line_id", sa.String(length=50), nullable=False, comment="TfL line ID (e.g., 'bakerloo', 'victoria')"
        ),
        sa.Column(
            "status_severity_description",
            sa.String(length=100),
            nullable=False,
            comment="Disruption status (e.g., 'Good Service', 'Minor Delays', 'Severe Delays')",
        ),
        sa.Column(
            "reason",
            sa.String(length=1000),
            nullable=True,
            comment="Full disruption reason text (nullable for good service)",
        ),
        sa.Column(
            "state_hash",
            sa.String(length=64),
            nullable=False,
            comment="SHA256 hash of {line_id, status, reason} for deduplication",
        ),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="When this state was detected by the alert service",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes
    op.create_index("ix_line_disruption_state_logs_line_id", "line_disruption_state_logs", ["line_id"])
    op.create_index("ix_line_disruption_state_logs_state_hash", "line_disruption_state_logs", ["state_hash"])
    op.create_index("ix_line_disruption_state_logs_detected_at", "line_disruption_state_logs", ["detected_at"])
    # Composite index for querying recent states for a line
    op.create_index("ix_line_disruption_logs_line_detected", "line_disruption_state_logs", ["line_id", "detected_at"])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index("ix_line_disruption_logs_line_detected", table_name="line_disruption_state_logs")
    op.drop_index("ix_line_disruption_state_logs_detected_at", table_name="line_disruption_state_logs")
    op.drop_index("ix_line_disruption_state_logs_state_hash", table_name="line_disruption_state_logs")
    op.drop_index("ix_line_disruption_state_logs_line_id", table_name="line_disruption_state_logs")

    # Drop table
    op.drop_table("line_disruption_state_logs")
