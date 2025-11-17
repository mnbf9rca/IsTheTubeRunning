"""add_route_station_index

Revision ID: 6675f5ef1429
Revises: 595219043932
Create Date: 2025-11-13 16:57:37.107767

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6675f5ef1429"
down_revision: str | Sequence[str] | None = "595219043932"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create route_station_index table for fast disruption lookups
    op.create_table(
        "route_station_index",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "route_id",
            sa.UUID(),
            nullable=False,
            comment="User's route ID",
        ),
        sa.Column(
            "line_tfl_id",
            sa.String(length=50),
            nullable=False,
            comment="TfL line ID (e.g., 'piccadilly', 'northern')",
        ),
        sa.Column(
            "station_naptan",
            sa.String(length=50),
            nullable=False,
            comment="Station NaPTAN code (e.g., '940GZZLUKSX')",
        ),
        sa.Column(
            "line_data_version",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Copy of Line.last_updated for staleness detection",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["route_id"],
            ["user_routes.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for efficient lookups
    # Primary lookup: "Which routes pass through station X on line Y?"
    op.create_index(
        op.f("ix_route_station_index_line_station"),
        "route_station_index",
        ["line_tfl_id", "station_naptan"],
        unique=False,
    )

    # Cleanup lookup: "Delete all index entries for route Z"
    op.create_index(
        op.f("ix_route_station_index_route"),
        "route_station_index",
        ["route_id"],
        unique=False,
    )

    # Staleness lookup: "Find routes with outdated index data"
    op.create_index(
        op.f("ix_route_station_index_line_data_version"),
        "route_station_index",
        ["line_data_version"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes in reverse order
    op.drop_index(
        op.f("ix_route_station_index_line_data_version"),
        table_name="route_station_index",
    )
    op.drop_index(op.f("ix_route_station_index_route"), table_name="route_station_index")
    op.drop_index(
        op.f("ix_route_station_index_line_station"),
        table_name="route_station_index",
    )

    # Drop table
    op.drop_table("route_station_index")
