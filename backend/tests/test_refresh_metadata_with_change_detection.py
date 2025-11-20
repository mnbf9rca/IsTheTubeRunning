"""Tests for refresh_metadata_with_change_detection method."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from app.models.tfl import DisruptionCategory, SeverityCode, StopType
from app.services.tfl_service import MetadataChangeDetectedError, TfLService
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_refresh_metadata_with_change_detection_no_changes(
    db_session: AsyncSession,
) -> None:
    """Test refresh when metadata hasn't changed."""
    now = datetime.now(UTC)

    # Create initial metadata
    severity_code = SeverityCode(
        mode_id="tube",
        severity_level=10,
        description="Severe Delays",
        last_updated=now,
    )
    category = DisruptionCategory(
        category_name="RealTime",
        description="Real-time disruption",
        last_updated=now,
    )
    stop_type = StopType(
        type_name="NaptanMetroStation",
        description="Metro station",
        last_updated=now,
    )

    db_session.add_all([severity_code, category, stop_type])
    await db_session.commit()

    # Create service
    tfl_service = TfLService(db=db_session)

    # Mock fetch methods to return fresh instances with same data (no changes)
    # Note: Must return NEW instances, not the same objects already in session
    with (
        patch.object(
            tfl_service,
            "fetch_severity_codes",
            new_callable=AsyncMock,
            return_value=[
                SeverityCode(mode_id="tube", severity_level=10, description="Severe Delays", last_updated=now)
            ],
        ),
        patch.object(
            tfl_service,
            "fetch_disruption_categories",
            new_callable=AsyncMock,
            return_value=[
                DisruptionCategory(category_name="RealTime", description="Real-time disruption", last_updated=now)
            ],
        ),
        patch.object(
            tfl_service,
            "fetch_stop_types",
            new_callable=AsyncMock,
            return_value=[StopType(type_name="NaptanMetroStation", description="Metro station", last_updated=now)],
        ),
    ):
        # Should not raise exception when no changes
        counts = await tfl_service.refresh_metadata_with_change_detection()

        assert counts == (1, 1, 1)  # 1 of each type


@pytest.mark.asyncio
async def test_refresh_metadata_with_change_detection_severity_codes_changed(
    db_session: AsyncSession,
) -> None:
    """Test refresh detects when severity codes change."""
    now = datetime.now(UTC)

    # Create initial metadata
    severity_code_before = SeverityCode(
        mode_id="tube",
        severity_level=10,
        description="Severe Delays",
        last_updated=now,
    )
    category = DisruptionCategory(
        category_name="RealTime",
        description="Real-time disruption",
        last_updated=now,
    )
    stop_type = StopType(
        type_name="NaptanMetroStation",
        description="Metro station",
        last_updated=now,
    )

    db_session.add_all([severity_code_before, category, stop_type])
    await db_session.commit()

    # Create service
    tfl_service = TfLService(db=db_session)

    # Mock fetch methods - severity codes have NEW item
    # Return fresh instances to avoid session conflicts
    with (
        patch.object(
            tfl_service,
            "fetch_severity_codes",
            new_callable=AsyncMock,
            return_value=[
                SeverityCode(mode_id="tube", severity_level=10, description="Severe Delays", last_updated=now),
                SeverityCode(
                    mode_id="tube", severity_level=6, description="Minor Delays", last_updated=now
                ),  # Added item
            ],
        ),
        patch.object(
            tfl_service,
            "fetch_disruption_categories",
            new_callable=AsyncMock,
            return_value=[
                DisruptionCategory(category_name="RealTime", description="Real-time disruption", last_updated=now)
            ],
        ),
        patch.object(
            tfl_service,
            "fetch_stop_types",
            new_callable=AsyncMock,
            return_value=[StopType(type_name="NaptanMetroStation", description="Metro station", last_updated=now)],
        ),
    ):
        # Should raise exception when changes detected
        with pytest.raises(MetadataChangeDetectedError) as exc_info:
            await tfl_service.refresh_metadata_with_change_detection()

        # Check exception details
        error = exc_info.value
        assert "severity_codes" in str(error)
        assert "changed_types" in error.details
        assert "severity_codes" in error.details["changed_types"]


@pytest.mark.asyncio
async def test_refresh_metadata_with_change_detection_categories_changed(
    db_session: AsyncSession,
) -> None:
    """Test refresh detects when disruption categories change."""
    now = datetime.now(UTC)

    # Create initial metadata
    severity_code = SeverityCode(
        mode_id="tube",
        severity_level=10,
        description="Severe Delays",
        last_updated=now,
    )
    category_before = DisruptionCategory(
        category_name="RealTime",
        description="Real-time disruption",
        last_updated=now,
    )
    stop_type = StopType(
        type_name="NaptanMetroStation",
        description="Metro station",
        last_updated=now,
    )

    db_session.add_all([severity_code, category_before, stop_type])
    await db_session.commit()

    # Create service
    tfl_service = TfLService(db=db_session)

    # Mock fetch methods - categories have NEW item
    # Return fresh instances to avoid session conflicts
    with (
        patch.object(
            tfl_service,
            "fetch_severity_codes",
            new_callable=AsyncMock,
            return_value=[
                SeverityCode(mode_id="tube", severity_level=10, description="Severe Delays", last_updated=now)
            ],
        ),
        patch.object(
            tfl_service,
            "fetch_disruption_categories",
            new_callable=AsyncMock,
            return_value=[
                DisruptionCategory(category_name="RealTime", description="Real-time disruption", last_updated=now),
                DisruptionCategory(
                    category_name="PlannedWork", description="Planned work", last_updated=now
                ),  # Added item
            ],
        ),
        patch.object(
            tfl_service,
            "fetch_stop_types",
            new_callable=AsyncMock,
            return_value=[StopType(type_name="NaptanMetroStation", description="Metro station", last_updated=now)],
        ),
    ):
        # Should raise exception when changes detected
        with pytest.raises(MetadataChangeDetectedError) as exc_info:
            await tfl_service.refresh_metadata_with_change_detection()

        error = exc_info.value
        assert "disruption_categories" in str(error)
        assert "disruption_categories" in error.details["changed_types"]


@pytest.mark.asyncio
async def test_refresh_metadata_with_change_detection_multiple_changes(
    db_session: AsyncSession,
) -> None:
    """Test refresh detects when multiple metadata types change."""
    now = datetime.now(UTC)

    # Create initial metadata
    severity_code_before = SeverityCode(
        mode_id="tube",
        severity_level=10,
        description="Severe Delays",
        last_updated=now,
    )
    category_before = DisruptionCategory(
        category_name="RealTime",
        description="Real-time disruption",
        last_updated=now,
    )
    stop_type_before = StopType(
        type_name="NaptanMetroStation",
        description="Metro station",
        last_updated=now,
    )

    db_session.add_all([severity_code_before, category_before, stop_type_before])
    await db_session.commit()

    # Create service
    tfl_service = TfLService(db=db_session)

    # Mock fetch methods - ALL have changes
    with (
        patch.object(
            tfl_service,
            "fetch_severity_codes",
            new_callable=AsyncMock,
            return_value=[
                SeverityCode(mode_id="tube", severity_level=10, description="Severe Delays", last_updated=now),
                SeverityCode(mode_id="tube", severity_level=6, description="Minor", last_updated=now),
            ],
        ),
        patch.object(
            tfl_service,
            "fetch_disruption_categories",
            new_callable=AsyncMock,
            return_value=[
                DisruptionCategory(category_name="RealTime", description="Real-time disruption", last_updated=now),
                DisruptionCategory(category_name="Planned", description="Planned", last_updated=now),
            ],
        ),
        patch.object(
            tfl_service,
            "fetch_stop_types",
            new_callable=AsyncMock,
            return_value=[
                StopType(type_name="NaptanMetroStation", description="Metro station", last_updated=now),
                StopType(type_name="NaptanRail", description="Rail", last_updated=now),
            ],
        ),
    ):
        # Should raise exception with all changes listed
        with pytest.raises(MetadataChangeDetectedError) as exc_info:
            await tfl_service.refresh_metadata_with_change_detection()

        error = exc_info.value
        assert len(error.details["changed_types"]) == 3
        assert "severity_codes" in error.details["changed_types"]
        assert "disruption_categories" in error.details["changed_types"]
        assert "stop_types" in error.details["changed_types"]


@pytest.mark.asyncio
async def test_refresh_metadata_with_change_detection_empty_database(
    db_session: AsyncSession,
) -> None:
    """Test refresh when database is initially empty."""
    now = datetime.now(UTC)

    # No initial data in database

    # Create service
    tfl_service = TfLService(db=db_session)

    # Mock fetch methods to return data
    with (
        patch.object(
            tfl_service,
            "fetch_severity_codes",
            new_callable=AsyncMock,
            return_value=[SeverityCode(mode_id="tube", severity_level=10, description="Severe", last_updated=now)],
        ),
        patch.object(
            tfl_service,
            "fetch_disruption_categories",
            new_callable=AsyncMock,
            return_value=[DisruptionCategory(category_name="RealTime", description="Real-time", last_updated=now)],
        ),
        patch.object(
            tfl_service,
            "fetch_stop_types",
            new_callable=AsyncMock,
            return_value=[StopType(type_name="NaptanMetroStation", description="Metro", last_updated=now)],
        ),
    ):
        # Should raise exception because empty -> populated is a change
        with pytest.raises(MetadataChangeDetectedError) as exc_info:
            await tfl_service.refresh_metadata_with_change_detection()

        error = exc_info.value
        # All three types changed (empty to populated)
        assert len(error.details["changed_types"]) == 3


@pytest.mark.asyncio
async def test_refresh_metadata_with_change_detection_preserves_commit_on_exception(
    db_session: AsyncSession,
) -> None:
    """Test that fetch methods still commit data even when exception is raised."""
    now = datetime.now(UTC)

    # Create initial metadata
    severity_code_before = SeverityCode(
        mode_id="tube",
        severity_level=10,
        description="Severe Delays",
        last_updated=now,
    )

    db_session.add(severity_code_before)
    await db_session.commit()

    # Count records before
    count_before = (await db_session.execute(select(SeverityCode))).scalars().all()
    assert len(count_before) == 1

    # Create service
    tfl_service = TfLService(db=db_session)

    # Mock fetch methods to return DIFFERENT data (will cause exception)
    # BUT fetch_severity_codes internally commits to database

    async def mock_fetch_severity_codes(use_cache: bool = True) -> list[SeverityCode]:
        # Simulate fetch method adding to database
        new_code = SeverityCode(
            mode_id="tube",
            severity_level=6,
            description="Minor Delays",
            last_updated=now,
        )
        db_session.add(new_code)
        await db_session.commit()
        # Return both old and new
        return [
            SeverityCode(mode_id="tube", severity_level=10, description="Severe Delays", last_updated=now),
            new_code,
        ]

    with (
        patch.object(
            tfl_service,
            "fetch_severity_codes",
            side_effect=mock_fetch_severity_codes,
        ),
        patch.object(
            tfl_service,
            "fetch_disruption_categories",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch.object(
            tfl_service,
            "fetch_stop_types",
            new_callable=AsyncMock,
            return_value=[],
        ),
        pytest.raises(MetadataChangeDetectedError),
    ):
        # Should raise exception
        await tfl_service.refresh_metadata_with_change_detection()

    # Check that new data WAS committed (fetch methods commit independently)
    count_after = (await db_session.execute(select(SeverityCode))).scalars().all()
    assert len(count_after) == 2, "Fetch method should have committed new data"


@pytest.mark.asyncio
async def test_refresh_metadata_with_change_detection_http_exception(
    db_session: AsyncSession,
) -> None:
    """Test refresh handles HTTPException from fetch methods."""
    now = datetime.now(UTC)

    # Create initial metadata
    severity_code = SeverityCode(
        mode_id="tube",
        severity_level=10,
        description="Severe Delays",
        last_updated=now,
    )

    db_session.add(severity_code)
    await db_session.commit()

    # Create service
    tfl_service = TfLService(db=db_session)

    # Mock fetch_severity_codes to raise HTTPException
    with (
        patch.object(
            tfl_service,
            "fetch_severity_codes",
            new_callable=AsyncMock,
            side_effect=HTTPException(status_code=503, detail="TfL API unavailable"),
        ),
    ):
        # Should re-raise HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await tfl_service.refresh_metadata_with_change_detection()

        assert exc_info.value.status_code == 503
        assert "TfL API unavailable" in exc_info.value.detail


@pytest.mark.asyncio
async def test_refresh_metadata_with_change_detection_generic_exception(
    db_session: AsyncSession,
) -> None:
    """Test refresh handles generic exceptions from fetch methods."""
    now = datetime.now(UTC)

    # Create initial metadata
    severity_code = SeverityCode(
        mode_id="tube",
        severity_level=10,
        description="Severe Delays",
        last_updated=now,
    )

    db_session.add(severity_code)
    await db_session.commit()

    # Create service
    tfl_service = TfLService(db=db_session)

    # Mock fetch_severity_codes to raise generic exception
    with (
        patch.object(
            tfl_service,
            "fetch_severity_codes",
            new_callable=AsyncMock,
            side_effect=ValueError("Unexpected error"),
        ),
    ):
        # Should wrap in HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await tfl_service.refresh_metadata_with_change_detection()

        assert exc_info.value.status_code == 503
        assert "Failed to refresh TfL metadata" in exc_info.value.detail
