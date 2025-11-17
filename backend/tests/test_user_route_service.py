"""Unit tests for UserRouteService."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from app.models.tfl import Line, Station
from app.models.user import User
from app.models.user_route import UserRoute
from app.schemas.routes import SegmentRequest
from app.services.user_route_service import UserRouteService
from sqlalchemy.ext.asyncio import AsyncSession


class TestUserRouteServiceUpsertSegments:
    """Tests for upsert_segments exception handling."""

    @pytest.mark.asyncio
    async def test_upsert_segments_rollback_on_exception(
        self,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test that database errors trigger rollback in upsert_segments."""
        # Create test data
        route = UserRoute(user_id=test_user.id, name="Test Route", active=True)
        db_session.add(route)

        line = Line(tfl_id="victoria", name="Victoria", last_updated=datetime.now(UTC))
        station1 = Station(
            tfl_id="st1",
            name="Station 1",
            latitude=51.5,
            longitude=-0.1,
            lines=["victoria"],
            last_updated=datetime.now(UTC),
        )
        station2 = Station(
            tfl_id="st2",
            name="Station 2",
            latitude=51.5,
            longitude=-0.1,
            lines=["victoria"],
            last_updated=datetime.now(UTC),
        )
        db_session.add_all([line, station1, station2])
        await db_session.commit()
        await db_session.refresh(route)
        await db_session.refresh(station1)
        await db_session.refresh(station2)
        await db_session.refresh(line)

        # Create service
        service = UserRouteService(db_session)

        # Create segments
        segments = [
            SegmentRequest(sequence=0, station_tfl_id=station1.tfl_id, line_tfl_id=line.tfl_id),
            SegmentRequest(sequence=1, station_tfl_id=station2.tfl_id, line_tfl_id=line.tfl_id),
        ]

        # Mock validation to pass, commit to fail, and rollback to verify it's called
        with (
            patch.object(service, "_validate_segments", return_value=None),
            patch.object(db_session, "commit", side_effect=Exception("Database error")),
            patch.object(db_session, "rollback", new_callable=AsyncMock) as mock_rollback,
            pytest.raises(Exception, match="Database error"),
        ):
            await service.upsert_segments(route.id, test_user.id, segments)

        # Verify rollback was called
        mock_rollback.assert_called_once()
