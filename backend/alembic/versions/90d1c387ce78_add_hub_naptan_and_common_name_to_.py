"""add_hub_naptan_and_common_name_to_stations

Revision ID: 90d1c387ce78
Revises: e5dfdd8388bc
Create Date: 2025-11-09 13:49:07.621945

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "90d1c387ce78"
down_revision: str | Sequence[str] | None = "e5dfdd8388bc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema: Add hub NaPTAN code fields to stations table.

    Adds hub_naptan_code and hub_common_name fields to support cross-mode
    interchange detection. These fields link stations at the same physical
    location (e.g., Seven Sisters rail and tube stations).
    """
    op.add_column(
        "stations",
        sa.Column(
            "hub_naptan_code",
            sa.String(length=50),
            nullable=True,
            comment="TfL hub NaPTAN code for interchange stations",
        ),
    )
    op.add_column(
        "stations",
        sa.Column(
            "hub_common_name",
            sa.String(length=255),
            nullable=True,
            comment="Common name for the hub (e.g., 'Seven Sisters')",
        ),
    )
    op.create_index(
        op.f("ix_stations_hub_naptan_code"),
        "stations",
        ["hub_naptan_code"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema: Remove hub NaPTAN code fields from stations table."""
    op.drop_index(op.f("ix_stations_hub_naptan_code"), table_name="stations")
    op.drop_column("stations", "hub_common_name")
    op.drop_column("stations", "hub_naptan_code")
