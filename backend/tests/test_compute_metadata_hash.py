"""Tests for _compute_metadata_hash helper function."""

from app.models.tfl import DisruptionCategory, SeverityCode, StopType
from app.services.tfl_service import _compute_metadata_hash


def test_compute_metadata_hash_severity_codes_stable() -> None:
    """Test that hash is stable for same severity codes."""
    codes = [
        SeverityCode(
            mode_id="tube",
            severity_level=10,
            description="Severe Delays",
        ),
        SeverityCode(
            mode_id="tube",
            severity_level=6,
            description="Minor Delays",
        ),
    ]

    hash1 = _compute_metadata_hash(codes)
    hash2 = _compute_metadata_hash(codes)

    assert hash1 == hash2
    assert len(hash1) == 64  # SHA256 produces 64 hex characters


def test_compute_metadata_hash_severity_codes_sorted() -> None:
    """Test that hash is same regardless of input order (items are sorted)."""
    codes_order1 = [
        SeverityCode(mode_id="tube", severity_level=10, description="Severe Delays"),
        SeverityCode(mode_id="tube", severity_level=6, description="Minor Delays"),
    ]

    codes_order2 = [
        SeverityCode(mode_id="tube", severity_level=6, description="Minor Delays"),
        SeverityCode(mode_id="tube", severity_level=10, description="Severe Delays"),
    ]

    hash1 = _compute_metadata_hash(codes_order1)
    hash2 = _compute_metadata_hash(codes_order2)

    assert hash1 == hash2, "Hash should be same regardless of input order"


def test_compute_metadata_hash_disruption_categories() -> None:
    """Test hash computation for disruption categories."""
    categories = [
        DisruptionCategory(category_name="RealTime", description="Real-time disruption"),
        DisruptionCategory(category_name="PlannedWork", description="Planned work"),
    ]

    hash1 = _compute_metadata_hash(categories)
    hash2 = _compute_metadata_hash(categories)

    assert hash1 == hash2
    assert len(hash1) == 64


def test_compute_metadata_hash_stop_types() -> None:
    """Test hash computation for stop types."""
    types = [
        StopType(type_name="NaptanMetroStation", description="Metro station"),
        StopType(type_name="NaptanRailStation", description="Rail station"),
    ]

    hash1 = _compute_metadata_hash(types)
    hash2 = _compute_metadata_hash(types)

    assert hash1 == hash2
    assert len(hash1) == 64


def test_compute_metadata_hash_empty_list() -> None:
    """Test hash computation for empty list."""
    # Empty list of severity codes
    hash_result = _compute_metadata_hash([])  # type: ignore[arg-type]

    assert isinstance(hash_result, str)
    assert len(hash_result) == 64
    # Hash of empty list "[]" should be consistent
    assert hash_result == _compute_metadata_hash([])  # type: ignore[arg-type]


def test_compute_metadata_hash_changes_when_data_changes() -> None:
    """Test that hash changes when data changes."""
    codes_before = [
        SeverityCode(mode_id="tube", severity_level=10, description="Severe Delays"),
    ]

    codes_after = [
        SeverityCode(mode_id="tube", severity_level=10, description="Severe Delays"),
        SeverityCode(mode_id="tube", severity_level=6, description="Minor Delays"),  # Added
    ]

    hash_before = _compute_metadata_hash(codes_before)
    hash_after = _compute_metadata_hash(codes_after)

    assert hash_before != hash_after, "Hash should change when data changes"


def test_compute_metadata_hash_detects_description_changes() -> None:
    """Test that hash changes when description changes."""
    codes_before = [
        SeverityCode(mode_id="tube", severity_level=10, description="Severe Delays"),
    ]

    codes_after = [
        SeverityCode(mode_id="tube", severity_level=10, description="Very Severe Delays"),
    ]

    hash_before = _compute_metadata_hash(codes_before)
    hash_after = _compute_metadata_hash(codes_after)

    assert hash_before != hash_after, "Hash should change when description changes"


def test_compute_metadata_hash_different_types_produce_different_hashes() -> None:
    """Test that different metadata types produce different hashes even with similar data."""
    severity_codes = [
        SeverityCode(mode_id="tube", severity_level=10, description="Test"),
    ]

    stop_types = [
        StopType(type_name="test", description="Test"),
    ]

    hash_codes = _compute_metadata_hash(severity_codes)
    hash_types = _compute_metadata_hash(stop_types)

    assert hash_codes != hash_types, "Different types should produce different hashes"
