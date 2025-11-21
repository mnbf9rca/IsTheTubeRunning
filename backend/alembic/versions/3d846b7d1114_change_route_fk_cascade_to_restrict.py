"""change_route_fk_cascade_to_restrict

Revision ID: 3d846b7d1114
Revises: 728def08ac79
Create Date: 2025-11-21 21:22:54.574454

Fix for Issue #233: Change foreign key CASCADE to RESTRICT for safety.

When soft delete is used everywhere, CASCADE foreign keys become a liability:
- If someone accidentally uses hard delete, CASCADE will cascade and lose data
- RESTRICT provides a safety net - database will reject hard delete attempts
- Application code handles soft delete cascades explicitly

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3d846b7d1114"
down_revision: str | Sequence[str] | None = "728def08ac79"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    Change all route-related foreign key constraints from CASCADE to RESTRICT.
    This prevents accidental data loss if hard DELETE is used instead of soft delete.
    """
    # user_routes.user_id → users.id
    op.drop_constraint("user_routes_user_id_fkey", "user_routes", type_="foreignkey")
    op.create_foreign_key(
        "user_routes_user_id_fkey",
        "user_routes",
        "users",
        ["user_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # user_route_segments.route_id → user_routes.id
    op.drop_constraint("user_route_segments_route_id_fkey", "user_route_segments", type_="foreignkey")
    op.create_foreign_key(
        "user_route_segments_route_id_fkey",
        "user_route_segments",
        "user_routes",
        ["route_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # user_route_segments.station_id → stations.id
    op.drop_constraint(
        "user_route_segments_station_id_fkey",
        "user_route_segments",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "user_route_segments_station_id_fkey",
        "user_route_segments",
        "stations",
        ["station_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # user_route_segments.line_id → lines.id
    op.drop_constraint("user_route_segments_line_id_fkey", "user_route_segments", type_="foreignkey")
    op.create_foreign_key(
        "user_route_segments_line_id_fkey",
        "user_route_segments",
        "lines",
        ["line_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # user_route_schedules.route_id → user_routes.id
    op.drop_constraint(
        "user_route_schedules_route_id_fkey",
        "user_route_schedules",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "user_route_schedules_route_id_fkey",
        "user_route_schedules",
        "user_routes",
        ["route_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # user_route_station_index.route_id → user_routes.id
    op.drop_constraint(
        "user_route_station_index_route_id_fkey",
        "user_route_station_index",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "user_route_station_index_route_id_fkey",
        "user_route_station_index",
        "user_routes",
        ["route_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # notification_preferences.route_id → user_routes.id
    op.drop_constraint(
        "notification_preferences_route_id_fkey",
        "notification_preferences",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "notification_preferences_route_id_fkey",
        "notification_preferences",
        "user_routes",
        ["route_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # NOTE: notification_logs.route_id → user_routes.id remains CASCADE
    # This is intentional - we want to preserve logs for analytics even when routes are deleted


def downgrade() -> None:
    """Downgrade schema.

    Restore CASCADE behavior on all foreign key constraints.
    """
    # user_routes.user_id → users.id
    op.drop_constraint("user_routes_user_id_fkey", "user_routes", type_="foreignkey")
    op.create_foreign_key(
        "user_routes_user_id_fkey",
        "user_routes",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # user_route_segments.route_id → user_routes.id
    op.drop_constraint("user_route_segments_route_id_fkey", "user_route_segments", type_="foreignkey")
    op.create_foreign_key(
        "user_route_segments_route_id_fkey",
        "user_route_segments",
        "user_routes",
        ["route_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # user_route_segments.station_id → stations.id
    op.drop_constraint(
        "user_route_segments_station_id_fkey",
        "user_route_segments",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "user_route_segments_station_id_fkey",
        "user_route_segments",
        "stations",
        ["station_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # user_route_segments.line_id → lines.id
    op.drop_constraint("user_route_segments_line_id_fkey", "user_route_segments", type_="foreignkey")
    op.create_foreign_key(
        "user_route_segments_line_id_fkey",
        "user_route_segments",
        "lines",
        ["line_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # user_route_schedules.route_id → user_routes.id
    op.drop_constraint(
        "user_route_schedules_route_id_fkey",
        "user_route_schedules",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "user_route_schedules_route_id_fkey",
        "user_route_schedules",
        "user_routes",
        ["route_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # user_route_station_index.route_id → user_routes.id
    op.drop_constraint(
        "user_route_station_index_route_id_fkey",
        "user_route_station_index",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "user_route_station_index_route_id_fkey",
        "user_route_station_index",
        "user_routes",
        ["route_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # notification_preferences.route_id → user_routes.id
    op.drop_constraint(
        "notification_preferences_route_id_fkey",
        "notification_preferences",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "notification_preferences_route_id_fkey",
        "notification_preferences",
        "user_routes",
        ["route_id"],
        ["id"],
        ondelete="CASCADE",
    )
