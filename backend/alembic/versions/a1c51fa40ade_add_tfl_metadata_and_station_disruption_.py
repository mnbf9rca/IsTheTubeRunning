"""Add TfL metadata and station disruption tables

Revision ID: a1c51fa40ade
Revises: 1c202b5d7d28
Create Date: 2025-11-05 09:59:33.131652

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1c51fa40ade"
down_revision: str | Sequence[str] | None = "1c202b5d7d28"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create severity_codes table
    op.create_table(
        "severity_codes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("severity_level", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("severity_level"),
    )
    op.create_index(
        op.f("ix_severity_codes_severity_level"),
        "severity_codes",
        ["severity_level"],
        unique=False,
    )

    # Create disruption_categories table
    op.create_table(
        "disruption_categories",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("category_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("category_name"),
    )
    op.create_index(
        op.f("ix_disruption_categories_category_name"),
        "disruption_categories",
        ["category_name"],
        unique=False,
    )

    # Create stop_types table
    op.create_table(
        "stop_types",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("type_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("type_name"),
    )
    op.create_index(op.f("ix_stop_types_type_name"), "stop_types", ["type_name"], unique=False)

    # Create station_disruptions table
    op.create_table(
        "station_disruptions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("station_id", sa.UUID(), nullable=False),
        sa.Column("disruption_category", sa.String(length=255), nullable=True),
        sa.Column("description", sa.String(length=1000), nullable=False),
        sa.Column("severity", sa.String(length=100), nullable=True),
        sa.Column("tfl_id", sa.String(length=100), nullable=False),
        sa.Column("created_at_source", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["station_id"],
            ["stations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_station_disruptions_station"),
        "station_disruptions",
        ["station_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_station_disruptions_station_id"),
        "station_disruptions",
        ["station_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_station_disruptions_tfl_id"),
        "station_disruptions",
        ["tfl_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_station_disruptions_tfl_id"), table_name="station_disruptions")
    op.drop_index(op.f("ix_station_disruptions_station_id"), table_name="station_disruptions")
    op.drop_index(op.f("ix_station_disruptions_station"), table_name="station_disruptions")
    op.drop_table("station_disruptions")
    op.drop_index(op.f("ix_stop_types_type_name"), table_name="stop_types")
    op.drop_table("stop_types")
    op.drop_index(
        op.f("ix_disruption_categories_category_name"),
        table_name="disruption_categories",
    )
    op.drop_table("disruption_categories")
    op.drop_index(op.f("ix_severity_codes_severity_level"), table_name="severity_codes")
    op.drop_table("severity_codes")
