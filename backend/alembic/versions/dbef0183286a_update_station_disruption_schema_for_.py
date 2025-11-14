"""update_station_disruption_schema_for_tfl_api_alignment

Revision ID: dbef0183286a
Revises: 6675f5ef1429
Create Date: 2025-11-14 08:52:12.314775

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "dbef0183286a"
down_revision: str | Sequence[str] | None = "6675f5ef1429"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    Changes to align StationDisruption model with TfL API DisruptedPoint structure:
    1. Rename disruption_category → type (matches TfL API field)
    2. Rename severity → appearance (matches TfL API field)
    3. Add end_date column (from TfL API toDate field)
    """
    # Add end_date column
    op.add_column(
        "station_disruptions",
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
    )

    # Rename disruption_category to type
    op.alter_column(
        "station_disruptions",
        "disruption_category",
        new_column_name="type",
    )

    # Rename severity to appearance
    op.alter_column(
        "station_disruptions",
        "severity",
        new_column_name="appearance",
    )


def downgrade() -> None:
    """Downgrade schema.

    Reverse the changes made in upgrade():
    1. Rename appearance → severity
    2. Rename type → disruption_category
    3. Remove end_date column
    """
    # Rename appearance back to severity
    op.alter_column(
        "station_disruptions",
        "appearance",
        new_column_name="severity",
    )

    # Rename type back to disruption_category
    op.alter_column(
        "station_disruptions",
        "type",
        new_column_name="disruption_category",
    )

    # Remove end_date column
    op.drop_column("station_disruptions", "end_date")
