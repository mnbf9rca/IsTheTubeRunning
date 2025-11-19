"""Tests for TfL service OpenTelemetry instrumentation."""

import os
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.models.tfl import Line
from app.services import tfl_service
from app.services.tfl_service import TfLService
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode
from pydantic_tfl_api.models import (
    Line as TflLine,
)
from pydantic_tfl_api.models import (
    Mode as TflMode,
)
from pydantic_tfl_api.models import (
    StopPoint as TflStopPoint,
)
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fixtures.otel import get_recorded_spans


# Re-enable OTEL for these tests
# conftest.py sets OTEL_SDK_DISABLED=true by default
@pytest.fixture(autouse=True)
def enable_otel_for_tests() -> Generator[None]:
    """Enable OTEL SDK for tests in this module."""
    original = os.environ.get("OTEL_SDK_DISABLED")
    if "OTEL_SDK_DISABLED" in os.environ:
        del os.environ["OTEL_SDK_DISABLED"]
    yield
    if original is not None:
        os.environ["OTEL_SDK_DISABLED"] = original
    elif "OTEL_SDK_DISABLED" in os.environ:
        del os.environ["OTEL_SDK_DISABLED"]


class MockResponse:
    """Mock response object for TfL API calls."""

    def __init__(
        self,
        data: Any,  # noqa: ANN401
        shared_expires: datetime | None = None,
        http_status_code: int = 200,
    ) -> None:
        """Initialize mock response."""
        # Create a RootModel-like content object
        content = MagicMock()
        content.root = data
        self.content = content
        self.shared_expires = shared_expires
        self.http_status_code = http_status_code


def create_mock_mode(mode_name: str = "tube") -> TflMode:
    """Create mock TfL Mode object."""
    return TflMode(modeName=mode_name)


def create_mock_line(
    id: str = "victoria",
    name: str = "Victoria",
    **kwargs: Any,  # noqa: ANN401
) -> TflLine:
    """Create mock TfL Line object."""
    return TflLine(id=id, name=name, **kwargs)


def create_mock_stop_point(
    id: str = "940GZZLUVIC",
    common_name: str = "Victoria",
    **kwargs: Any,  # noqa: ANN401
) -> TflStopPoint:
    """Create mock TfL StopPoint object."""
    if "modes" not in kwargs:
        kwargs["modes"] = ["tube"]
    return TflStopPoint(id=id, commonName=common_name, **kwargs)


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create mock database session."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def mock_cache() -> AsyncMock:
    """Create mock cache."""
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    return cache


@pytest.fixture
def tfl_service_with_mock(mock_db_session: AsyncMock, mock_cache: AsyncMock) -> TfLService:
    """Create TfLService with mocked dependencies."""
    service = TfLService(db=mock_db_session)
    service.cache = mock_cache
    return service


class TestTflApiSpans:
    """Test class for TfL API span instrumentation."""

    @pytest.mark.asyncio
    async def test_fetch_available_modes_creates_span(
        self,
        tfl_service_with_mock: TfLService,
        in_memory_span_exporter: InMemorySpanExporter,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Test that fetch_available_modes creates a span with correct attributes."""
        exporter = in_memory_span_exporter
        test_tracer = test_tracer_provider.get_tracer(tfl_service.__name__)

        # Setup mock response
        mock_modes = [create_mock_mode("tube"), create_mock_mode("dlr")]
        mock_response = MockResponse(
            data=mock_modes,
            shared_expires=datetime.now(UTC) + timedelta(days=7),
        )

        # Patch the tracer and mock the API call
        with (
            patch.object(tfl_service, "tracer", test_tracer),
            patch.object(
                tfl_service_with_mock.line_client,
                "MetaModes",
                new_callable=AsyncMock,
                return_value=mock_response,
            ),
        ):
            await tfl_service_with_mock.fetch_available_modes()

        # Verify span was created
        spans = get_recorded_spans(exporter)
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "tfl.api.MetaModes"
        assert span.attributes is not None
        assert span.attributes["tfl.api.endpoint"] == "MetaModes"
        assert span.attributes["tfl.api.client"] == "line_client"
        assert span.attributes["peer.service"] == "api.tfl.gov.uk"
        assert span.attributes["http.status_code"] == 200

    @pytest.mark.asyncio
    async def test_fetch_lines_creates_span_per_mode(
        self,
        tfl_service_with_mock: TfLService,
        in_memory_span_exporter: InMemorySpanExporter,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Test that fetch_lines creates a span for each mode fetched."""
        exporter = in_memory_span_exporter
        test_tracer = test_tracer_provider.get_tracer(tfl_service.__name__)

        # Setup mock response
        mock_line = create_mock_line("victoria", "Victoria")
        mock_response = MockResponse(
            data=[mock_line],
            shared_expires=datetime.now(UTC) + timedelta(days=1),
        )

        # Patch the tracer and mock the API call (will be called twice, once per mode)
        with (
            patch.object(tfl_service, "tracer", test_tracer),
            patch.object(
                tfl_service_with_mock.line_client,
                "GetByModeByPathModes",
                new_callable=AsyncMock,
                return_value=mock_response,
            ),
        ):
            await tfl_service_with_mock.fetch_lines(modes=["tube", "dlr"])

        # Verify spans were created (one per mode)
        spans = get_recorded_spans(exporter)
        assert len(spans) == 2

        for span in spans:
            assert span.name == "tfl.api.GetByModeByPathModes"
            assert span.attributes is not None
            assert span.attributes["tfl.api.endpoint"] == "GetByModeByPathModes"
            assert span.attributes["tfl.api.client"] == "line_client"
            assert "tfl.api.mode" in span.attributes

    @pytest.mark.asyncio
    async def test_extract_hub_fields_creates_span_when_hub_exists(
        self,
        tfl_service_with_mock: TfLService,
        in_memory_span_exporter: InMemorySpanExporter,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Test that _extract_hub_fields creates a span when hub code exists."""
        exporter = in_memory_span_exporter
        test_tracer = test_tracer_provider.get_tracer(tfl_service.__name__)

        # Create stop point with hub code
        stop_point = create_mock_stop_point()
        object.__setattr__(stop_point, "hubNaptanCode", "HUBVIC")

        # Create hub data response
        hub_data = MagicMock()
        hub_data.commonName = "Victoria"
        mock_response = MockResponse(data=[hub_data])

        # Patch the tracer and mock the API call
        with (
            patch.object(tfl_service, "tracer", test_tracer),
            patch.object(
                tfl_service_with_mock.stoppoint_client,
                "GetByPathIdsQueryIncludeCrowdingData",
                new_callable=AsyncMock,
                return_value=mock_response,
            ),
        ):
            await tfl_service_with_mock._extract_hub_fields(stop_point)

        # Verify span was created
        spans = get_recorded_spans(exporter)
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "tfl.api.GetByPathIdsQueryIncludeCrowdingData"
        assert span.attributes is not None
        assert span.attributes["tfl.api.hub_code"] == "HUBVIC"

    @pytest.mark.asyncio
    async def test_extract_hub_fields_no_span_when_no_hub(
        self,
        tfl_service_with_mock: TfLService,
        in_memory_span_exporter: InMemorySpanExporter,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Test that _extract_hub_fields creates no span when hub code is None."""
        exporter = in_memory_span_exporter
        test_tracer = test_tracer_provider.get_tracer(tfl_service.__name__)

        # Create stop point without hub code
        stop_point = create_mock_stop_point()
        # hubNaptanCode is None by default

        with patch.object(tfl_service, "tracer", test_tracer):
            hub_code, hub_name = await tfl_service_with_mock._extract_hub_fields(stop_point)

        # Verify no span was created
        spans = get_recorded_spans(exporter)
        assert len(spans) == 0

        # Verify return values
        assert hub_code is None
        assert hub_name is None

    @pytest.mark.asyncio
    async def test_fetch_route_sequence_creates_span(
        self,
        tfl_service_with_mock: TfLService,
        in_memory_span_exporter: InMemorySpanExporter,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Test that _fetch_route_sequence creates a span with line_id and direction."""
        exporter = in_memory_span_exporter
        test_tracer = test_tracer_provider.get_tracer(tfl_service.__name__)

        # Setup mock response
        mock_route_sequence = MagicMock()
        mock_route_sequence.stopPointSequences = []
        mock_response = MockResponse(data=mock_route_sequence)
        mock_response.content = mock_route_sequence

        with (
            patch.object(tfl_service, "tracer", test_tracer),
            patch.object(
                tfl_service_with_mock.line_client,
                "RouteSequenceByPathIdPathDirectionQueryServiceTypesQueryExcludeCrowding",
                new_callable=AsyncMock,
                return_value=mock_response,
            ),
        ):
            await tfl_service_with_mock._fetch_route_sequence("victoria", "outbound")

        # Verify span was created
        spans = get_recorded_spans(exporter)
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "tfl.api.RouteSequenceByPathIdPathDirectionQueryServiceTypesQueryExcludeCrowding"
        assert span.attributes is not None
        assert span.attributes["tfl.api.line_id"] == "victoria"
        assert span.attributes["tfl.api.direction"] == "outbound"

    @pytest.mark.asyncio
    async def test_cache_hit_does_not_create_span(
        self,
        tfl_service_with_mock: TfLService,
        in_memory_span_exporter: InMemorySpanExporter,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Test that cache hits don't create TfL API spans."""
        exporter = in_memory_span_exporter
        test_tracer = test_tracer_provider.get_tracer(tfl_service.__name__)

        # Set up cache to return data
        cached_modes = ["tube", "dlr"]
        tfl_service_with_mock.cache.get = AsyncMock(return_value=cached_modes)

        with patch.object(tfl_service, "tracer", test_tracer):
            result = await tfl_service_with_mock.fetch_available_modes()

        # Verify no spans were created
        spans = get_recorded_spans(exporter)
        assert len(spans) == 0

        # Verify result came from cache
        assert result == cached_modes

    @pytest.mark.asyncio
    async def test_fetch_severity_codes_creates_span(
        self,
        tfl_service_with_mock: TfLService,
        in_memory_span_exporter: InMemorySpanExporter,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Test that fetch_severity_codes creates a span with correct attributes."""
        exporter = in_memory_span_exporter
        test_tracer = test_tracer_provider.get_tracer(tfl_service.__name__)

        # Setup mock response - severity codes response
        mock_severity = MagicMock()
        mock_severity.severityLevel = 0
        mock_severity.modeName = "tube"
        mock_severity.description = "Good Service"
        mock_response = MockResponse(
            data=[mock_severity],
            shared_expires=datetime.now(UTC) + timedelta(days=7),
        )

        # Mock database operations - these methods do async db.execute calls
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        tfl_service_with_mock.db.execute = AsyncMock(return_value=mock_result)
        tfl_service_with_mock.db.commit = AsyncMock()
        tfl_service_with_mock.db.refresh = AsyncMock()

        with (
            patch.object(tfl_service, "tracer", test_tracer),
            patch.object(
                tfl_service_with_mock.line_client,
                "MetaSeverity",
                new_callable=AsyncMock,
                return_value=mock_response,
            ),
        ):
            await tfl_service_with_mock.fetch_severity_codes()

        # Verify span was created
        spans = get_recorded_spans(exporter)
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "tfl.api.MetaSeverity"
        assert span.attributes is not None
        assert span.attributes["tfl.api.endpoint"] == "MetaSeverity"
        assert span.attributes["tfl.api.client"] == "line_client"
        assert span.attributes["peer.service"] == "api.tfl.gov.uk"
        assert span.attributes["http.status_code"] == 200

    @pytest.mark.asyncio
    async def test_fetch_disruption_categories_creates_span(
        self,
        tfl_service_with_mock: TfLService,
        in_memory_span_exporter: InMemorySpanExporter,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Test that fetch_disruption_categories creates a span with correct attributes."""
        exporter = in_memory_span_exporter
        test_tracer = test_tracer_provider.get_tracer(tfl_service.__name__)

        # Setup mock response - disruption categories response
        mock_response = MockResponse(
            data=["RealTime", "PlannedWork", "Information"],
            shared_expires=datetime.now(UTC) + timedelta(days=7),
        )

        # Mock database operations
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        tfl_service_with_mock.db.execute = AsyncMock(return_value=mock_result)
        tfl_service_with_mock.db.commit = AsyncMock()
        tfl_service_with_mock.db.refresh = AsyncMock()

        with (
            patch.object(tfl_service, "tracer", test_tracer),
            patch.object(
                tfl_service_with_mock.line_client,
                "MetaDisruptionCategories",
                new_callable=AsyncMock,
                return_value=mock_response,
            ),
        ):
            await tfl_service_with_mock.fetch_disruption_categories()

        # Verify span was created
        spans = get_recorded_spans(exporter)
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "tfl.api.MetaDisruptionCategories"
        assert span.attributes is not None
        assert span.attributes["tfl.api.endpoint"] == "MetaDisruptionCategories"
        assert span.attributes["tfl.api.client"] == "line_client"
        assert span.attributes["peer.service"] == "api.tfl.gov.uk"
        assert span.attributes["http.status_code"] == 200

    @pytest.mark.asyncio
    async def test_fetch_stop_types_creates_span(
        self,
        tfl_service_with_mock: TfLService,
        in_memory_span_exporter: InMemorySpanExporter,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Test that fetch_stop_types creates a span with correct attributes."""
        exporter = in_memory_span_exporter
        test_tracer = test_tracer_provider.get_tracer(tfl_service.__name__)

        # Setup mock response - stop types response
        mock_response = MockResponse(
            data=["NaptanMetroStation", "NaptanRailStation"],
            shared_expires=datetime.now(UTC) + timedelta(days=7),
        )

        # Mock database operations
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        tfl_service_with_mock.db.execute = AsyncMock(return_value=mock_result)
        tfl_service_with_mock.db.commit = AsyncMock()
        tfl_service_with_mock.db.refresh = AsyncMock()

        with (
            patch.object(tfl_service, "tracer", test_tracer),
            patch.object(
                tfl_service_with_mock.stoppoint_client,
                "MetaStopTypes",
                new_callable=AsyncMock,
                return_value=mock_response,
            ),
        ):
            await tfl_service_with_mock.fetch_stop_types()

        # Verify span was created
        spans = get_recorded_spans(exporter)
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "tfl.api.MetaStopTypes"
        assert span.attributes is not None
        assert span.attributes["tfl.api.endpoint"] == "MetaStopTypes"
        assert span.attributes["tfl.api.client"] == "stoppoint_client"
        assert span.attributes["peer.service"] == "api.tfl.gov.uk"
        assert span.attributes["http.status_code"] == 200

    @pytest.mark.asyncio
    async def test_fetch_line_disruptions_creates_span(
        self,
        tfl_service_with_mock: TfLService,
        in_memory_span_exporter: InMemorySpanExporter,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Test that fetch_line_disruptions creates a span with correct attributes."""
        exporter = in_memory_span_exporter
        test_tracer = test_tracer_provider.get_tracer(tfl_service.__name__)

        # Setup mock response - line status response
        mock_line_status = MagicMock()
        mock_line_status.id = "victoria"
        mock_line_status.name = "Victoria"
        mock_line_status.lineStatuses = []
        mock_response = MockResponse(
            data=[mock_line_status],
            shared_expires=datetime.now(UTC) + timedelta(minutes=2),
        )

        # Create mock Line objects for fetch_lines to return from cache
        mock_line = MagicMock(spec=Line)
        mock_line.tfl_id = "victoria"
        mock_line.name = "Victoria"

        # Set up cache to return lines (bypass fetch_lines API call)
        cache_key = tfl_service_with_mock._build_modes_cache_key("lines", ["tube"])
        tfl_service_with_mock.cache.get = AsyncMock(side_effect=lambda key: [mock_line] if key == cache_key else None)

        with (
            patch.object(tfl_service, "tracer", test_tracer),
            patch.object(
                tfl_service_with_mock.line_client,
                "StatusByIdsByPathIdsQueryDetail",
                new_callable=AsyncMock,
                return_value=mock_response,
            ),
        ):
            await tfl_service_with_mock.fetch_line_disruptions(modes=["tube"])

        # Verify span was created (only the disruptions span, not the lines span)
        spans = get_recorded_spans(exporter)
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "tfl.api.StatusByIdsByPathIdsQueryDetail"
        assert span.attributes is not None
        assert span.attributes["tfl.api.endpoint"] == "StatusByIdsByPathIdsQueryDetail"
        assert span.attributes["tfl.api.client"] == "line_client"
        assert span.attributes["tfl.api.line_count"] == 1
        assert span.attributes["peer.service"] == "api.tfl.gov.uk"
        assert span.attributes["http.status_code"] == 200

    @pytest.mark.asyncio
    async def test_fetch_station_disruptions_creates_span(
        self,
        tfl_service_with_mock: TfLService,
        in_memory_span_exporter: InMemorySpanExporter,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Test that fetch_station_disruptions creates a span for each mode."""
        exporter = in_memory_span_exporter
        test_tracer = test_tracer_provider.get_tracer(tfl_service.__name__)

        # Setup mock response - station disruptions response
        mock_response = MockResponse(
            data=[],  # Empty list - no disruptions
            shared_expires=datetime.now(UTC) + timedelta(minutes=2),
        )

        with (
            patch.object(tfl_service, "tracer", test_tracer),
            patch.object(
                tfl_service_with_mock.stoppoint_client,
                "DisruptionByModeByPathModesQueryIncludeRouteBlockedStops",
                new_callable=AsyncMock,
                return_value=mock_response,
            ),
        ):
            await tfl_service_with_mock.fetch_station_disruptions(modes=["tube"])

        # Verify span was created
        spans = get_recorded_spans(exporter)
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "tfl.api.DisruptionByModeByPathModesQueryIncludeRouteBlockedStops"
        assert span.attributes is not None
        assert span.attributes["tfl.api.endpoint"] == "DisruptionByModeByPathModesQueryIncludeRouteBlockedStops"
        assert span.attributes["tfl.api.client"] == "stoppoint_client"
        assert span.attributes["tfl.api.mode"] == "tube"
        assert span.attributes["peer.service"] == "api.tfl.gov.uk"
        assert span.attributes["http.status_code"] == 200


class TestTflApiSpanErrorHandling:
    """Test class for TfL API span error recording.

    The OpenTelemetry SDK automatically records exceptions and sets span status
    to ERROR when an exception occurs within a span context. These tests verify
    that behavior works correctly with the tfl_api_span helper.
    """

    @pytest.mark.asyncio
    async def test_span_records_exception_on_api_error(
        self,
        tfl_service_with_mock: TfLService,
        in_memory_span_exporter: InMemorySpanExporter,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Test that span records exception when API call fails."""
        exporter = in_memory_span_exporter
        test_tracer = test_tracer_provider.get_tracer(tfl_service.__name__)

        # Mock API to raise an exception
        api_error = Exception("TfL API connection error")

        with (
            patch.object(tfl_service, "tracer", test_tracer),
            patch.object(
                tfl_service_with_mock.line_client,
                "MetaModes",
                new_callable=AsyncMock,
                side_effect=api_error,
            ),
            pytest.raises(Exception, match="Failed to fetch transport modes"),
        ):
            await tfl_service_with_mock.fetch_available_modes()

        # Verify span was created and has error status
        spans = get_recorded_spans(exporter)
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "tfl.api.MetaModes"
        assert span.status.status_code == StatusCode.ERROR

        # Verify exception was recorded
        assert len(span.events) >= 1
        exception_event = next((e for e in span.events if e.name == "exception"), None)
        assert exception_event is not None
        assert "TfL API connection error" in str(exception_event.attributes)

    @pytest.mark.asyncio
    async def test_span_records_exception_on_fetch_lines_error(
        self,
        tfl_service_with_mock: TfLService,
        in_memory_span_exporter: InMemorySpanExporter,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Test that span records exception when fetch_lines API call fails."""
        exporter = in_memory_span_exporter
        test_tracer = test_tracer_provider.get_tracer(tfl_service.__name__)

        # Mock database execute to succeed for the delete
        tfl_service_with_mock.db.execute = AsyncMock()

        # Mock API to raise an exception
        api_error = Exception("Network timeout")

        with (
            patch.object(tfl_service, "tracer", test_tracer),
            patch.object(
                tfl_service_with_mock.line_client,
                "GetByModeByPathModes",
                new_callable=AsyncMock,
                side_effect=api_error,
            ),
            pytest.raises(Exception, match="Failed to fetch lines"),
        ):
            await tfl_service_with_mock.fetch_lines(modes=["tube"])

        # Verify span was created and has error status
        spans = get_recorded_spans(exporter)
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "tfl.api.GetByModeByPathModes"
        assert span.status.status_code == StatusCode.ERROR

    @pytest.mark.asyncio
    async def test_span_records_exception_on_hub_fetch_error(
        self,
        tfl_service_with_mock: TfLService,
        in_memory_span_exporter: InMemorySpanExporter,
        test_tracer_provider: TracerProvider,
    ) -> None:
        """Test that span records exception when hub API call fails."""
        exporter = in_memory_span_exporter
        test_tracer = test_tracer_provider.get_tracer(tfl_service.__name__)

        # Create stop point with hub code
        stop_point = create_mock_stop_point()
        object.__setattr__(stop_point, "hubNaptanCode", "HUBVIC")

        # Mock API to raise an exception
        api_error = Exception("Hub API error")

        with (
            patch.object(tfl_service, "tracer", test_tracer),
            patch.object(
                tfl_service_with_mock.stoppoint_client,
                "GetByPathIdsQueryIncludeCrowdingData",
                new_callable=AsyncMock,
                side_effect=api_error,
            ),
        ):
            # _extract_hub_fields catches exceptions and returns original hub_code, None for hub_name
            hub_code, hub_name = await tfl_service_with_mock._extract_hub_fields(stop_point)

        # Verify span was created and has error status
        spans = get_recorded_spans(exporter)
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "tfl.api.GetByPathIdsQueryIncludeCrowdingData"
        assert span.status.status_code == StatusCode.ERROR

        # Verify the method returns hub_code (from stop_point) and None for hub_name on error
        assert hub_code == "HUBVIC"
        assert hub_name is None
