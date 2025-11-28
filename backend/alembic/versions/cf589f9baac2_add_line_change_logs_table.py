"""add_line_change_logs_table

Revision ID: cf589f9baac2
Revises: 237745010854
Create Date: 2025-11-28 09:52:28.770124

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cf589f9baac2"
down_revision: str | Sequence[str] | None = "237745010854"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "line_change_logs",
        sa.Column(
            "tfl_id",
            sa.String(length=50),
            nullable=False,
            comment="TfL line ID (e.g., 'victoria', 'northern')",
        ),
        sa.Column(
            "change_type",
            sa.String(length=20),
            nullable=False,
            comment="Type of change: 'created', 'updated'",
        ),
        sa.Column(
            "changed_fields",
            sa.JSON(),
            nullable=False,
            comment="List of fields that changed: ['name', 'mode', 'route_variants']",
        ),
        sa.Column(
            "old_values",
            sa.JSON(),
            nullable=True,
            comment="Previous values of changed fields (NULL for 'created')",
        ),
        sa.Column(
            "new_values",
            sa.JSON(),
            nullable=False,
            comment="New values of changed fields",
        ),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="When this change was detected",
        ),
        sa.Column(
            "trace_id",
            sa.String(length=32),
            nullable=True,
            comment="OpenTelemetry trace ID for correlation with distributed traces",
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    # Create indexes
    op.create_index(
        "ix_line_change_logs_tfl_detected",
        "line_change_logs",
        ["tfl_id", "detected_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_line_change_logs_tfl_id"),
        "line_change_logs",
        ["tfl_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_line_change_logs_detected_at"),
        "line_change_logs",
        ["detected_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_line_change_logs_trace_id"),
        "line_change_logs",
        ["trace_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_line_change_logs_trace_id"), table_name="line_change_logs")
    op.drop_index(op.f("ix_line_change_logs_detected_at"), table_name="line_change_logs")
    op.drop_index(op.f("ix_line_change_logs_tfl_id"), table_name="line_change_logs")
    op.drop_index("ix_line_change_logs_tfl_detected", table_name="line_change_logs")
    op.drop_table("line_change_logs")
