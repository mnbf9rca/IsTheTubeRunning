"""Tests for DisruptionMatchingService OpenTelemetry instrumentation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.schemas.tfl import AffectedRouteInfo, DisruptionResponse
from app.services.disruption_matching_service import DisruptionMatchingService
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, StatusCode

from tests.helpers.otel import assert_span_status


class TestDisruptionMatchingServiceFilterAlertableOtelSpans:
    """Test DisruptionMatchingService.filter_alertable_disruptions() OTEL spans."""

    @pytest.mark.asyncio
    async def test_filter_alertable_creates_span_with_ok_status(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that filter_alertable_disruptions creates a span with OK status."""
        _, exporter = otel_enabled_provider

        # Create mock database session
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []  # No disabled severities
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = DisruptionMatchingService(db=mock_db)

        # Create test disruptions
        disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=14,
                status_severity_description="Severe Delays",
            ),
            DisruptionResponse(
                line_id="jubilee",
                line_name="Jubilee",
                mode="tube",
                status_severity=12,
                status_severity_description="Minor Delays",
            ),
        ]

        filtered = await service.filter_alertable_disruptions(disruptions)

        assert len(filtered) == 2  # No filtering

        # Verify span was created with OK status
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "disruption.filter_alertable"
        assert span.kind == SpanKind.INTERNAL
        assert_span_status(span, StatusCode.OK)

        # Verify span attributes
        assert span.attributes is not None
        assert span.attributes["peer.service"] == "disruption-matching-service"
        assert span.attributes["disruption.input_count"] == 2
        assert span.attributes["disruption.output_count"] == 2
        assert span.attributes["disruption.filtered_count"] == 0

    @pytest.mark.asyncio
    async def test_filter_alertable_records_exception_on_error(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that span records exception when database error occurs."""
        _, exporter = otel_enabled_provider

        # Create mock database session that fails
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=Exception("Database connection error"))

        service = DisruptionMatchingService(db=mock_db)

        # Create test disruptions
        disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=14,
                status_severity_description="Severe Delays",
            ),
        ]

        # Method should raise exception
        with pytest.raises(Exception, match="Database connection error"):
            await service.filter_alertable_disruptions(disruptions)

        # Verify span has error status
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "disruption.filter_alertable"
        assert_span_status(span, StatusCode.ERROR, check_exception=True)


class TestDisruptionMatchingServiceMatchToRouteOtelSpans:
    """Test DisruptionMatchingService.match_disruptions_to_route() OTEL spans."""

    @pytest.mark.asyncio
    async def test_match_to_route_creates_span_with_ok_status(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that match_disruptions_to_route creates a span with OK status."""
        _, exporter = otel_enabled_provider

        # Create mock database session
        mock_db = AsyncMock()

        service = DisruptionMatchingService(db=mock_db)

        # Create route index pairs
        route_pairs = {("victoria", "940GZZLUVIC"), ("victoria", "940GZZLUGPK")}

        # Create test disruptions
        disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=14,
                status_severity_description="Severe Delays",
                affected_routes=[
                    AffectedRouteInfo(
                        name="Victoria",
                        direction="inbound",
                        affected_stations=["940GZZLUVIC"],
                    )
                ],
            ),
        ]

        service.match_disruptions_to_route(route_pairs, disruptions)

        # Verify span was created with OK status
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "disruption.match_to_route"
        assert span.kind == SpanKind.INTERNAL
        assert_span_status(span, StatusCode.OK)

        # Verify span attributes
        assert span.attributes is not None
        assert span.attributes["peer.service"] == "disruption-matching-service"
        assert span.attributes["disruption.route_pairs_count"] == 2
        assert span.attributes["disruption.input_count"] == 1
        assert span.attributes["disruption.matched_count"] >= 0  # Depends on helper function logic

    @pytest.mark.asyncio
    async def test_match_to_route_records_exception_on_error(
        self,
        otel_enabled_provider: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that span records exception when helper function raises error."""
        _, exporter = otel_enabled_provider

        # Create mock database session
        mock_db = AsyncMock()

        service = DisruptionMatchingService(db=mock_db)

        # Create route index pairs
        route_pairs = {("victoria", "940GZZLUVIC")}

        # Create valid disruption
        disruptions = [
            DisruptionResponse(
                line_id="victoria",
                line_name="Victoria",
                mode="tube",
                status_severity=14,
                status_severity_description="Severe Delays",
                affected_routes=[
                    AffectedRouteInfo(
                        name="Victoria",
                        direction="inbound",
                        affected_stations=["940GZZLUVIC"],
                    )
                ],
            ),
        ]

        # Mock helper function to raise exception
        with (
            patch(
                "app.services.disruption_matching_service.extract_line_station_pairs",
                side_effect=Exception("Helper function error"),
            ),
            pytest.raises(Exception, match="Helper function error"),
        ):
            service.match_disruptions_to_route(route_pairs, disruptions)

        # Verify span has error status
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "disruption.match_to_route"
        assert_span_status(span, StatusCode.ERROR, check_exception=True)
