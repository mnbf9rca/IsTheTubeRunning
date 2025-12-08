"""add_is_cleared_state_to_alert_disabled_severities

Adds is_cleared_state column to alert_disabled_severities table to distinguish
between cleared states (Good Service, No Issues) and suppressed states (Service Closed).

This enables issue #361: Alert if disruption clears during notification window.

Revision ID: 1025d77921da
Revises: 1f4d6532d88a
Create Date: 2025-12-08 08:40:18.392507

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1025d77921da"
down_revision: str | Sequence[str] | None = "1f4d6532d88a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Step 1: Add is_cleared_state column with default False
    op.add_column(
        "alert_disabled_severities",
        sa.Column("is_cleared_state", sa.Boolean(), nullable=False, server_default="false"),
    )

    # Step 2: Update existing "Good Service" (severity 10) rows to is_cleared_state=True
    op.execute(
        sa.text(
            """
            UPDATE alert_disabled_severities
            SET is_cleared_state = true
            WHERE severity_level = 10
            """
        )
    )

    # Step 3: Add "No Issues" (severity 18) for each mode with is_cleared_state=True
    # List of TfL modes that support severity level 18 (No Issues)
    tfl_modes = [
        "tube",
        "dlr",
        "overground",
        "elizabeth-line",
        "tram",
        "cable-car",
        "river-bus",
        "bus",
        "cycle-hire",
        "river-tour",
    ]

    for mode in tfl_modes:
        op.execute(
            sa.text(
                """
                INSERT INTO alert_disabled_severities (id, mode_id, severity_level, is_cleared_state, created_at, updated_at)
                VALUES (gen_random_uuid(), :mode_id, 18, true, now(), now())
                ON CONFLICT DO NOTHING
                """
            ).bindparams(mode_id=mode)
        )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove "No Issues" (severity 18) entries that were added in upgrade
    op.execute(
        sa.text(
            """
            DELETE FROM alert_disabled_severities
            WHERE severity_level = 18 AND is_cleared_state = true
            """
        )
    )

    # Drop the is_cleared_state column
    op.drop_column("alert_disabled_severities", "is_cleared_state")
