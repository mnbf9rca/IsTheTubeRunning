"""expand text columns for disruption descriptions

Revision ID: cea4031bd399
Revises: cf589f9baac2
Create Date: 2025-11-30 20:11:08.529441

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cea4031bd399"
down_revision: str | Sequence[str] | None = "cf589f9baac2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema - expand VARCHAR(1000) columns to TEXT for disruption descriptions."""
    # Expand LineDisruptionStateLog.reason (primary fix for issue #297)
    # TfL API can return disruption reasons exceeding 1000 characters
    op.alter_column(
        "line_disruption_state_logs",
        "reason",
        existing_type=sa.String(length=1000),
        type_=sa.Text(),
        existing_nullable=True,
    )

    # Expand StationDisruption.description (preventative fix)
    # TfL API station disruption descriptions may also exceed 1000 characters
    op.alter_column(
        "station_disruptions",
        "description",
        existing_type=sa.String(length=1000),
        type_=sa.Text(),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema - revert TEXT columns to VARCHAR(1000)."""
    # WARNING: Downgrade may truncate data if any values exceed 1000 characters
    op.alter_column(
        "line_disruption_state_logs",
        "reason",
        existing_type=sa.Text(),
        type_=sa.String(length=1000),
        existing_nullable=True,
    )

    op.alter_column(
        "station_disruptions",
        "description",
        existing_type=sa.Text(),
        type_=sa.String(length=1000),
        existing_nullable=False,
    )
