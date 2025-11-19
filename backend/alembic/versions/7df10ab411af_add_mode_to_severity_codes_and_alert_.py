"""add_mode_to_severity_codes_and_alert_disabled_severities

Revision ID: 7df10ab411af
Revises: 8ed2312f54f3
Create Date: 2025-11-19 08:15:48.224661

"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7df10ab411af"
down_revision: str | Sequence[str] | None = "8ed2312f54f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# All TfL transport modes that may have severity codes
TFL_MODES = [
    "tube",
    "dlr",
    "overground",
    "elizabeth-line",
    "tram",
    "tfl-rail",
    "cable-car",
    "river-bus",
    "national-rail",
]


def upgrade() -> None:
    """Upgrade schema."""
    # Create the alert_disabled_severities table
    op.create_table(
        "alert_disabled_severities",
        sa.Column(
            "mode_id",
            sa.String(length=50),
            nullable=False,
            comment="Transport mode (e.g., 'tube', 'dlr', 'overground')",
        ),
        sa.Column("severity_level", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mode_id", "severity_level", name="uq_alert_disabled_severity_mode_level"),
    )
    op.create_index(
        op.f("ix_alert_disabled_severities_mode_id"),
        "alert_disabled_severities",
        ["mode_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_alert_disabled_severities_severity_level"),
        "alert_disabled_severities",
        ["severity_level"],
        unique=False,
    )

    # Clear existing severity_codes data (table should be empty, but handle gracefully)
    # This is needed because existing rows don't have mode_id
    op.execute("DELETE FROM severity_codes")

    # Add mode_id column to severity_codes
    op.add_column(
        "severity_codes",
        sa.Column(
            "mode_id",
            sa.String(length=50),
            nullable=False,
            comment="Transport mode (e.g., 'tube', 'dlr', 'overground')",
        ),
    )

    # Update indexes and constraints on severity_codes
    op.drop_index(op.f("ix_severity_codes_severity_level"), table_name="severity_codes")
    op.create_index(
        op.f("ix_severity_codes_severity_level"),
        "severity_codes",
        ["severity_level"],
        unique=False,
    )
    op.create_index(
        op.f("ix_severity_codes_mode_id"),
        "severity_codes",
        ["mode_id"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_severity_code_mode_level",
        "severity_codes",
        ["mode_id", "severity_level"],
    )

    # Populate alert_disabled_severities with severity_level=10 (Good Service) for all modes
    # This means "Good Service" will NOT trigger alerts
    now = datetime.now(UTC)
    for mode in TFL_MODES:
        new_id = str(uuid.uuid4())
        op.execute(
            sa.text(
                f"""
                INSERT INTO alert_disabled_severities (id, mode_id, severity_level, created_at, updated_at)
                VALUES ('{new_id}'::uuid, :mode_id, :severity_level, :created_at, :updated_at)
                """
            ).bindparams(
                mode_id=mode,
                severity_level=10,  # Good Service
                created_at=now,
                updated_at=now,
            )
        )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove the unique constraint and new indexes from severity_codes
    op.drop_constraint("uq_severity_code_mode_level", "severity_codes", type_="unique")
    op.drop_index(op.f("ix_severity_codes_mode_id"), table_name="severity_codes")
    op.drop_index(op.f("ix_severity_codes_severity_level"), table_name="severity_codes")

    # Restore original unique index on severity_level
    op.create_index(
        op.f("ix_severity_codes_severity_level"),
        "severity_codes",
        ["severity_level"],
        unique=True,
    )

    # Remove mode_id column
    op.drop_column("severity_codes", "mode_id")

    # Drop alert_disabled_severities table
    op.drop_index(
        op.f("ix_alert_disabled_severities_severity_level"),
        table_name="alert_disabled_severities",
    )
    op.drop_index(
        op.f("ix_alert_disabled_severities_mode_id"),
        table_name="alert_disabled_severities",
    )
    op.drop_table("alert_disabled_severities")
