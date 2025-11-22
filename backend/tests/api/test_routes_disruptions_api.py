"""Tests for GET /routes/disruptions API endpoint."""

from collections.abc import AsyncGenerator, Callable
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from app.core.database import get_db
from app.main import app
from app.models.tfl import AlertDisabledSeverity, Line, Station
from app.models.user import User
from app.models.user_route import UserRoute, UserRouteSegment
from app.models.user_route_index import UserRouteStationIndex
from app.schemas.tfl import AffectedRouteInfo, DisruptionResponse
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.helpers.jwt_helpers import MockJWTGenerator
from tests.helpers.railway_network import create_test_station


class TestRouteDisruptionsAPI:
    """Test /routes/disruptions endpoint."""

    @pytest.fixture(autouse=True)
    async def setup_test(self, db_session: AsyncSession) -> AsyncGenerator[None]:
        """Set up test database dependency override."""

        async def override_get_db() -> AsyncGenerator[AsyncSession]:
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        yield
        app.dependency_overrides.clear()

    @pytest.fixture
    async def piccadilly_line(self, db_session: AsyncSession) -> Line:
        """Create Piccadilly line."""
        line = Line(tfl_id="piccadilly", name="Piccadilly", mode="tube", last_updated=datetime.now(UTC))
        db_session.add(line)
        await db_session.commit()
        await db_session.refresh(line)
        return line

    @pytest.fixture
    async def district_line(self, db_session: AsyncSession) -> Line:
        """Create District line."""
        line = Line(tfl_id="district", name="District", mode="tube", last_updated=datetime.now(UTC))
        db_session.add(line)
        await db_session.commit()
        await db_session.refresh(line)
        return line

    @pytest.fixture
    async def station_ksx(self, db_session: AsyncSession) -> Station:
        """Create King's Cross station."""
        station = create_test_station(
            tfl_id="940GZZLUKSX",
            name="King's Cross St. Pancras",
            lines=["piccadilly"],
        )
        db_session.add(station)
        await db_session.commit()
        await db_session.refresh(station)
        return station

    @pytest.fixture
    async def station_rsq(self, db_session: AsyncSession) -> Station:
        """Create Russell Square station."""
        station = create_test_station(
            tfl_id="940GZZLURSQ",
            name="Russell Square",
            lines=["piccadilly"],
        )
        db_session.add(station)
        await db_session.commit()
        await db_session.refresh(station)
        return station

    @pytest.fixture
    async def station_hbn(self, db_session: AsyncSession) -> Station:
        """Create Holborn station."""
        station = create_test_station(
            tfl_id="940GZZLUHBN",
            name="Holborn",
            lines=["piccadilly"],
        )
        db_session.add(station)
        await db_session.commit()
        await db_session.refresh(station)
        return station

    @pytest.fixture
    async def station_emb(self, db_session: AsyncSession) -> Station:
        """Create Embankment station (District line)."""
        station = create_test_station(
            tfl_id="940GZZLUEMB",
            name="Embankment",
            lines=["district"],
        )
        db_session.add(station)
        await db_session.commit()
        await db_session.refresh(station)
        return station

    @pytest.fixture
    async def test_route_with_index(
        self,
        db_session: AsyncSession,
        test_user: User,
        piccadilly_line: Line,
        station_ksx: Station,
        station_rsq: Station,
        station_hbn: Station,
    ) -> UserRoute:
        """Create test route with populated UserRouteStationIndex."""
        # Create route
        route = UserRoute(
            user_id=test_user.id,
            name="Test Route",
            active=True,
            timezone="Europe/London",
        )
        db_session.add(route)
        await db_session.flush()

        # Create segments
        segment0 = UserRouteSegment(
            route_id=route.id,
            sequence=0,
            station_id=station_ksx.id,
            line_id=piccadilly_line.id,
        )
        segment1 = UserRouteSegment(
            route_id=route.id,
            sequence=1,
            station_id=station_rsq.id,
            line_id=piccadilly_line.id,
        )
        segment2 = UserRouteSegment(
            route_id=route.id,
            sequence=2,
            station_id=station_hbn.id,
            line_id=None,  # Destination
        )
        db_session.add_all([segment0, segment1, segment2])
        await db_session.flush()

        # Create UserRouteStationIndex entries
        index0 = UserRouteStationIndex(
            route_id=route.id,
            line_tfl_id=piccadilly_line.tfl_id,
            station_naptan=station_ksx.tfl_id,
            line_data_version=datetime.now(UTC),
        )
        index1 = UserRouteStationIndex(
            route_id=route.id,
            line_tfl_id=piccadilly_line.tfl_id,
            station_naptan=station_rsq.tfl_id,
            line_data_version=datetime.now(UTC),
        )
        index2 = UserRouteStationIndex(
            route_id=route.id,
            line_tfl_id=piccadilly_line.tfl_id,
            station_naptan=station_hbn.tfl_id,
            line_data_version=datetime.now(UTC),
        )
        db_session.add_all([index0, index1, index2])
        await db_session.commit()
        await db_session.refresh(route)
        return route

    @pytest.fixture
    async def inactive_route_with_index(
        self,
        db_session: AsyncSession,
        test_user: User,
        piccadilly_line: Line,
        station_ksx: Station,
        station_rsq: Station,
    ) -> UserRoute:
        """Create inactive route with index."""
        route = UserRoute(
            user_id=test_user.id,
            name="Inactive Route",
            active=False,
            timezone="Europe/London",
        )
        db_session.add(route)
        await db_session.flush()

        # Create segments
        segment0 = UserRouteSegment(
            route_id=route.id,
            sequence=0,
            station_id=station_ksx.id,
            line_id=piccadilly_line.id,
        )
        segment1 = UserRouteSegment(
            route_id=route.id,
            sequence=1,
            station_id=station_rsq.id,
            line_id=None,
        )
        db_session.add_all([segment0, segment1])
        await db_session.flush()

        # Create index
        index0 = UserRouteStationIndex(
            route_id=route.id,
            line_tfl_id=piccadilly_line.tfl_id,
            station_naptan=station_ksx.tfl_id,
            line_data_version=datetime.now(UTC),
        )
        index1 = UserRouteStationIndex(
            route_id=route.id,
            line_tfl_id=piccadilly_line.tfl_id,
            station_naptan=station_rsq.tfl_id,
            line_data_version=datetime.now(UTC),
        )
        db_session.add_all([index0, index1])
        await db_session.commit()
        await db_session.refresh(route)
        return route

    @pytest.fixture
    def sample_disruptions(self) -> list[DisruptionResponse]:
        """Sample TfL disruptions for testing."""
        return [
            DisruptionResponse(
                line_id="piccadilly",
                line_name="Piccadilly",
                mode="tube",
                status_severity=9,
                status_severity_description="Minor Delays",
                reason="Signal failure at Russell Square",
                affected_routes=[
                    AffectedRouteInfo(
                        name="Cockfosters → Heathrow Terminal 5",
                        direction="outbound",
                        affected_stations=["940GZZLURSQ", "940GZZLUHBN"],
                    )
                ],
            )
        ]

    @pytest.fixture
    def auth_headers_for_user_func(self) -> Callable[[User], dict[str, str]]:
        """Return a function that generates auth headers for a user."""

        def _generate_headers(user: User) -> dict[str, str]:
            token = MockJWTGenerator.generate(auth0_id=user.external_id)
            return {"Authorization": f"Bearer {token}"}

        return _generate_headers

    # ==================== Test Cases ====================

    @pytest.mark.asyncio
    async def test_get_disruptions_success(
        self,
        async_client_with_db: AsyncClient,
        test_user: User,
        test_route_with_index: UserRoute,
        sample_disruptions: list[DisruptionResponse],
        auth_headers_for_user_func: Callable[[User], dict[str, str]],
    ) -> None:
        """Test getting disruptions for user's routes."""
        with patch("app.api.routes.TfLService") as mock_tfl:
            mock_instance = AsyncMock()
            mock_instance.fetch_line_disruptions = AsyncMock(return_value=sample_disruptions)
            mock_tfl.return_value = mock_instance

            response = await async_client_with_db.get(
                "/api/v1/routes/disruptions",
                headers=auth_headers_for_user_func(test_user),
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["route_id"] == str(test_route_with_index.id)
            assert data[0]["route_name"] == "Test Route"
            assert data[0]["disruption"]["line_id"] == "piccadilly"
            assert data[0]["disruption"]["status_severity"] == 9
            assert len(data[0]["affected_segments"]) > 0
            assert len(data[0]["affected_stations"]) > 0
            # Verify affected stations are those matching the disruption
            assert "940GZZLURSQ" in data[0]["affected_stations"]
            assert "940GZZLUHBN" in data[0]["affected_stations"]

    @pytest.mark.asyncio
    async def test_get_disruptions_no_routes(
        self,
        async_client_with_db: AsyncClient,
        test_user: User,
        auth_headers_for_user_func: Callable[[User], dict[str, str]],
    ) -> None:
        """Test with user who has no routes."""
        response = await async_client_with_db.get(
            "/api/v1/routes/disruptions",
            headers=auth_headers_for_user_func(test_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data == []

    @pytest.mark.asyncio
    async def test_get_disruptions_no_disruptions(
        self,
        async_client_with_db: AsyncClient,
        test_user: User,
        test_route_with_index: UserRoute,
        auth_headers_for_user_func: Callable[[User], dict[str, str]],
    ) -> None:
        """Test with routes but no disruptions."""
        with patch("app.api.routes.TfLService") as mock_tfl:
            mock_instance = AsyncMock()
            mock_instance.fetch_line_disruptions = AsyncMock(return_value=[])
            mock_tfl.return_value = mock_instance

            response = await async_client_with_db.get(
                "/api/v1/routes/disruptions",
                headers=auth_headers_for_user_func(test_user),
            )

            assert response.status_code == 200
            data = response.json()
            assert data == []

    @pytest.mark.asyncio
    async def test_get_disruptions_different_line(
        self,
        async_client_with_db: AsyncClient,
        test_user: User,
        test_route_with_index: UserRoute,
        auth_headers_for_user_func: Callable[[User], dict[str, str]],
    ) -> None:
        """Test disruptions on different line don't match."""
        # Create disruption on District line (route is on Piccadilly)
        district_disruptions = [
            DisruptionResponse(
                line_id="district",
                line_name="District",
                mode="tube",
                status_severity=9,
                status_severity_description="Minor Delays",
                reason="Signal failure",
                affected_routes=[
                    AffectedRouteInfo(
                        name="Upminster → Ealing Broadway",
                        direction="westbound",
                        affected_stations=["940GZZLUEMB"],
                    )
                ],
            )
        ]

        with patch("app.api.routes.TfLService") as mock_tfl:
            mock_instance = AsyncMock()
            mock_instance.fetch_line_disruptions = AsyncMock(return_value=district_disruptions)
            mock_tfl.return_value = mock_instance

            response = await async_client_with_db.get(
                "/api/v1/routes/disruptions",
                headers=auth_headers_for_user_func(test_user),
            )

            assert response.status_code == 200
            data = response.json()
            assert data == []

    @pytest.mark.asyncio
    async def test_get_disruptions_different_stations(
        self,
        async_client_with_db: AsyncClient,
        test_user: User,
        test_route_with_index: UserRoute,
        station_emb: Station,
        auth_headers_for_user_func: Callable[[User], dict[str, str]],
    ) -> None:
        """Test disruptions on same line but different stations don't match."""
        # Disruption on Piccadilly line but at station not on route
        disruptions = [
            DisruptionResponse(
                line_id="piccadilly",
                line_name="Piccadilly",
                mode="tube",
                status_severity=9,
                status_severity_description="Minor Delays",
                reason="Signal failure",
                affected_routes=[
                    AffectedRouteInfo(
                        name="Cockfosters → Heathrow Terminal 5",
                        direction="outbound",
                        # Station not on the test route
                        affected_stations=["940GZZLUCGN"],  # Covent Garden
                    )
                ],
            )
        ]

        with patch("app.api.routes.TfLService") as mock_tfl:
            mock_instance = AsyncMock()
            mock_instance.fetch_line_disruptions = AsyncMock(return_value=disruptions)
            mock_tfl.return_value = mock_instance

            response = await async_client_with_db.get(
                "/api/v1/routes/disruptions",
                headers=auth_headers_for_user_func(test_user),
            )

            assert response.status_code == 200
            data = response.json()
            assert data == []

    @pytest.mark.asyncio
    async def test_get_disruptions_unauthenticated(
        self,
        async_client_with_db: AsyncClient,
    ) -> None:
        """Test endpoint requires authentication."""
        response = await async_client_with_db.get("/api/v1/routes/disruptions")

        # Auth middleware returns 403 when no token is provided in DEBUG mode
        assert response.status_code in [401, 403]

    @pytest.mark.asyncio
    async def test_get_disruptions_active_only_default(
        self,
        async_client_with_db: AsyncClient,
        test_user: User,
        test_route_with_index: UserRoute,
        inactive_route_with_index: UserRoute,
        sample_disruptions: list[DisruptionResponse],
        auth_headers_for_user_func: Callable[[User], dict[str, str]],
    ) -> None:
        """Test active_only=true is default and excludes inactive routes."""
        with patch("app.api.routes.TfLService") as mock_tfl:
            mock_instance = AsyncMock()
            mock_instance.fetch_line_disruptions = AsyncMock(return_value=sample_disruptions)
            mock_tfl.return_value = mock_instance

            response = await async_client_with_db.get(
                "/api/v1/routes/disruptions",
                headers=auth_headers_for_user_func(test_user),
            )

            assert response.status_code == 200
            data = response.json()
            # Should only return disruptions for active route
            route_ids = {item["route_id"] for item in data}
            assert str(test_route_with_index.id) in route_ids
            assert str(inactive_route_with_index.id) not in route_ids

    @pytest.mark.asyncio
    async def test_get_disruptions_include_inactive(
        self,
        async_client_with_db: AsyncClient,
        test_user: User,
        test_route_with_index: UserRoute,
        inactive_route_with_index: UserRoute,
        sample_disruptions: list[DisruptionResponse],
        auth_headers_for_user_func: Callable[[User], dict[str, str]],
    ) -> None:
        """Test active_only=false includes inactive routes."""
        with patch("app.api.routes.TfLService") as mock_tfl:
            mock_instance = AsyncMock()
            mock_instance.fetch_line_disruptions = AsyncMock(return_value=sample_disruptions)
            mock_tfl.return_value = mock_instance

            response = await async_client_with_db.get(
                "/api/v1/routes/disruptions?active_only=false",
                headers=auth_headers_for_user_func(test_user),
            )

            assert response.status_code == 200
            data = response.json()
            # Should return disruptions for both routes
            route_ids = {item["route_id"] for item in data}
            assert str(test_route_with_index.id) in route_ids
            assert str(inactive_route_with_index.id) in route_ids

    @pytest.mark.asyncio
    async def test_get_disruptions_only_inactive_routes_with_active_only(
        self,
        async_client_with_db: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        piccadilly_line: Line,
        station_ksx: Station,
        auth_headers_for_user_func: Callable[[User], dict[str, str]],
    ) -> None:
        """Test active_only=true when user has only inactive routes (early return optimization)."""
        # Create two inactive routes
        route1 = UserRoute(
            user_id=test_user.id,
            name="Inactive Route 1",
            active=False,
            timezone="Europe/London",
        )
        route2 = UserRoute(
            user_id=test_user.id,
            name="Inactive Route 2",
            active=False,
            timezone="Europe/London",
        )
        db_session.add_all([route1, route2])
        await db_session.flush()

        # Add segments to make them valid routes
        segment1 = UserRouteSegment(
            route_id=route1.id,
            sequence=0,
            station_id=station_ksx.id,
            line_id=None,
        )
        segment2 = UserRouteSegment(
            route_id=route2.id,
            sequence=0,
            station_id=station_ksx.id,
            line_id=None,
        )
        db_session.add_all([segment1, segment2])
        await db_session.commit()

        # Should return empty list without calling TfL API (early return optimization)
        # We intentionally don't mock TfLService to verify it's not called
        response = await async_client_with_db.get(
            "/api/v1/routes/disruptions?active_only=true",
            headers=auth_headers_for_user_func(test_user),
        )

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_get_disruptions_tfl_api_failure(
        self,
        async_client_with_db: AsyncClient,
        test_user: User,
        test_route_with_index: UserRoute,
        auth_headers_for_user_func: Callable[[User], dict[str, str]],
    ) -> None:
        """Test TfL API failure returns 503."""
        with patch("app.api.routes.TfLService") as mock_tfl:
            mock_instance = AsyncMock()
            mock_instance.fetch_line_disruptions = AsyncMock(side_effect=Exception("TfL API unavailable"))
            mock_tfl.return_value = mock_instance

            response = await async_client_with_db.get(
                "/api/v1/routes/disruptions",
                headers=auth_headers_for_user_func(test_user),
            )

            assert response.status_code == 503
            assert "TfL API unavailable" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_disruptions_multiple_routes(
        self,
        async_client_with_db: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_route_with_index: UserRoute,
        piccadilly_line: Line,
        district_line: Line,
        station_emb: Station,
        auth_headers_for_user_func: Callable[[User], dict[str, str]],
    ) -> None:
        """Test multiple routes and disruptions."""
        # Create second route on District line
        route2 = UserRoute(
            user_id=test_user.id,
            name="District Route",
            active=True,
            timezone="Europe/London",
        )
        db_session.add(route2)
        await db_session.flush()

        segment = UserRouteSegment(
            route_id=route2.id,
            sequence=0,
            station_id=station_emb.id,
            line_id=None,
        )
        db_session.add(segment)
        await db_session.flush()

        index = UserRouteStationIndex(
            route_id=route2.id,
            line_tfl_id=district_line.tfl_id,
            station_naptan=station_emb.tfl_id,
            line_data_version=datetime.now(UTC),
        )
        db_session.add(index)
        await db_session.commit()

        # Create disruptions for both lines
        disruptions = [
            DisruptionResponse(
                line_id="piccadilly",
                line_name="Piccadilly",
                mode="tube",
                status_severity=9,
                status_severity_description="Minor Delays",
                reason="Signal failure",
                affected_routes=[
                    AffectedRouteInfo(
                        name="Route 1",
                        direction="outbound",
                        affected_stations=["940GZZLURSQ"],
                    )
                ],
            ),
            DisruptionResponse(
                line_id="district",
                line_name="District",
                mode="tube",
                status_severity=8,
                status_severity_description="Severe Delays",
                reason="Broken rail",
                affected_routes=[
                    AffectedRouteInfo(
                        name="Route 2",
                        direction="westbound",
                        affected_stations=["940GZZLUEMB"],
                    )
                ],
            ),
        ]

        with patch("app.api.routes.TfLService") as mock_tfl:
            mock_instance = AsyncMock()
            mock_instance.fetch_line_disruptions = AsyncMock(return_value=disruptions)
            mock_tfl.return_value = mock_instance

            response = await async_client_with_db.get(
                "/api/v1/routes/disruptions",
                headers=auth_headers_for_user_func(test_user),
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            route_ids = {item["route_id"] for item in data}
            assert str(test_route_with_index.id) in route_ids
            assert str(route2.id) in route_ids

    @pytest.mark.asyncio
    async def test_get_disruptions_severity_filtering(
        self,
        async_client_with_db: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_route_with_index: UserRoute,
        auth_headers_for_user_func: Callable[[User], dict[str, str]],
    ) -> None:
        """Test non-alertable disruptions are filtered out."""
        # Check if severity level 10 for tube mode already exists
        result = await db_session.execute(
            select(AlertDisabledSeverity).where(
                AlertDisabledSeverity.mode_id == "tube",
                AlertDisabledSeverity.severity_level == 10,
            )
        )
        existing = result.scalar_one_or_none()
        if not existing:
            # Add severity level 10 (Good Service) to disabled list
            disabled = AlertDisabledSeverity(mode_id="tube", severity_level=10)
            db_session.add(disabled)
            await db_session.commit()

        # Create disruptions with both alertable and non-alertable severities
        disruptions = [
            DisruptionResponse(
                line_id="piccadilly",
                line_name="Piccadilly",
                mode="tube",
                status_severity=10,  # Good Service - should be filtered
                status_severity_description="Good Service",
                reason=None,
                affected_routes=[
                    AffectedRouteInfo(
                        name="Route 1",
                        direction="outbound",
                        affected_stations=["940GZZLURSQ"],
                    )
                ],
            ),
            DisruptionResponse(
                line_id="piccadilly",
                line_name="Piccadilly",
                mode="tube",
                status_severity=9,  # Minor Delays - should be included
                status_severity_description="Minor Delays",
                reason="Signal failure",
                affected_routes=[
                    AffectedRouteInfo(
                        name="Route 1",
                        direction="outbound",
                        affected_stations=["940GZZLURSQ"],
                    )
                ],
            ),
        ]

        with patch("app.api.routes.TfLService") as mock_tfl:
            mock_instance = AsyncMock()
            mock_instance.fetch_line_disruptions = AsyncMock(return_value=disruptions)
            mock_tfl.return_value = mock_instance

            response = await async_client_with_db.get(
                "/api/v1/routes/disruptions",
                headers=auth_headers_for_user_func(test_user),
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["disruption"]["status_severity"] == 9
            assert data[0]["disruption"]["status_severity_description"] == "Minor Delays"

    @pytest.mark.asyncio
    async def test_get_disruptions_soft_deleted_routes_excluded(
        self,
        async_client_with_db: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_route_with_index: UserRoute,
        sample_disruptions: list[DisruptionResponse],
        auth_headers_for_user_func: Callable[[User], dict[str, str]],
    ) -> None:
        """Test soft-deleted routes are excluded."""
        # Soft-delete the route
        test_route_with_index.deleted_at = datetime.now(UTC)
        db_session.add(test_route_with_index)
        await db_session.commit()

        with patch("app.api.routes.TfLService") as mock_tfl:
            mock_instance = AsyncMock()
            mock_instance.fetch_line_disruptions = AsyncMock(return_value=sample_disruptions)
            mock_tfl.return_value = mock_instance

            response = await async_client_with_db.get(
                "/api/v1/routes/disruptions",
                headers=auth_headers_for_user_func(test_user),
            )

            assert response.status_code == 200
            data = response.json()
            assert data == []

    @pytest.mark.asyncio
    async def test_get_disruptions_response_structure(
        self,
        async_client_with_db: AsyncClient,
        test_user: User,
        test_route_with_index: UserRoute,
        sample_disruptions: list[DisruptionResponse],
        auth_headers_for_user_func: Callable[[User], dict[str, str]],
    ) -> None:
        """Test response structure is correct."""
        with patch("app.api.routes.TfLService") as mock_tfl:
            mock_instance = AsyncMock()
            mock_instance.fetch_line_disruptions = AsyncMock(return_value=sample_disruptions)
            mock_tfl.return_value = mock_instance

            response = await async_client_with_db.get(
                "/api/v1/routes/disruptions",
                headers=auth_headers_for_user_func(test_user),
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1

            item = data[0]
            # Verify all required fields are present
            assert "route_id" in item
            assert "route_name" in item
            assert "disruption" in item
            assert "affected_segments" in item
            assert "affected_stations" in item

            # Verify route_id is a valid UUID
            assert UUID(item["route_id"])

            # Verify disruption structure
            disruption = item["disruption"]
            assert "line_id" in disruption
            assert "line_name" in disruption
            assert "mode" in disruption
            assert "status_severity" in disruption
            assert "status_severity_description" in disruption

            # Verify affected_segments is a list of integers
            assert isinstance(item["affected_segments"], list)
            assert all(isinstance(seg, int) for seg in item["affected_segments"])

            # Verify affected_stations is a list of strings
            assert isinstance(item["affected_stations"], list)
            assert all(isinstance(stn, str) for stn in item["affected_stations"])

    @pytest.mark.asyncio
    async def test_multiple_disruptions_on_same_route(
        self,
        async_client_with_db: AsyncClient,
        test_user: User,
        test_route_with_index: UserRoute,
        auth_headers_for_user_func: Callable[[User], dict[str, str]],
    ) -> None:
        """Test multiple disruptions on the same route create separate response entries."""
        # Create two disruptions on the same line/route
        disruptions = [
            DisruptionResponse(
                line_id="piccadilly",
                line_name="Piccadilly",
                mode="tube",
                status_severity=9,
                status_severity_description="Minor Delays",
                reason="Signal failure at Russell Square",
                affected_routes=[
                    AffectedRouteInfo(
                        name="Cockfosters → Heathrow Terminal 5",
                        direction="outbound",
                        affected_stations=["940GZZLURSQ"],
                    )
                ],
            ),
            DisruptionResponse(
                line_id="piccadilly",
                line_name="Piccadilly",
                mode="tube",
                status_severity=8,
                status_severity_description="Severe Delays",
                reason="Track maintenance at Holborn",
                affected_routes=[
                    AffectedRouteInfo(
                        name="Cockfosters → Heathrow Terminal 5",
                        direction="outbound",
                        affected_stations=["940GZZLUHBN"],
                    )
                ],
            ),
        ]

        with patch("app.api.routes.TfLService") as mock_tfl:
            mock_instance = AsyncMock()
            mock_instance.fetch_line_disruptions = AsyncMock(return_value=disruptions)
            mock_tfl.return_value = mock_instance

            response = await async_client_with_db.get(
                "/api/v1/routes/disruptions",
                headers=auth_headers_for_user_func(test_user),
            )

            assert response.status_code == 200
            data = response.json()
            # Should have 2 entries - one for each disruption on the route
            assert len(data) == 2
            # All entries should be for the same route
            route_ids = {item["route_id"] for item in data}
            assert len(route_ids) == 1
            assert str(test_route_with_index.id) in route_ids
            # Verify each disruption is represented
            severities = {item["disruption"]["status_severity"] for item in data}
            assert 9 in severities
            assert 8 in severities

    @pytest.mark.asyncio
    async def test_get_disruptions_empty_affected_stations(
        self,
        async_client_with_db: AsyncClient,
        test_user: User,
        test_route_with_index: UserRoute,
        auth_headers_for_user_func: Callable[[User], dict[str, str]],
    ) -> None:
        """Test disruption with empty affected_stations list doesn't match route."""
        disruptions = [
            DisruptionResponse(
                line_id="piccadilly",
                line_name="Piccadilly",
                mode="tube",
                status_severity=9,
                status_severity_description="Minor Delays",
                reason="General disruption",
                affected_routes=[
                    AffectedRouteInfo(
                        name="Cockfosters → Heathrow Terminal 5",
                        direction="outbound",
                        affected_stations=[],  # Empty affected stations
                    )
                ],
            )
        ]

        with patch("app.api.routes.TfLService") as mock_tfl:
            mock_instance = AsyncMock()
            mock_instance.fetch_line_disruptions = AsyncMock(return_value=disruptions)
            mock_tfl.return_value = mock_instance

            response = await async_client_with_db.get(
                "/api/v1/routes/disruptions",
                headers=auth_headers_for_user_func(test_user),
            )

            assert response.status_code == 200
            data = response.json()
            # Should have no entries because disruption has no affected stations
            assert len(data) == 0
