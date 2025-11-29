"""OpenTelemetry test helper functions."""

from typing import TYPE_CHECKING

from opentelemetry.trace import StatusCode

if TYPE_CHECKING:
    from opentelemetry.sdk.trace import ReadableSpan
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


def get_recorded_spans(exporter: "InMemorySpanExporter") -> list["ReadableSpan"]:
    """
    Get all recorded spans from the exporter.

    Helper function for retrieving and asserting spans in tests.

    Args:
        exporter: InMemorySpanExporter to retrieve spans from

    Returns:
        List of recorded spans

    Example:
        >>> spans = get_recorded_spans(in_memory_span_exporter)
        >>> assert len(spans) == 1
        >>> assert spans[0].name == "GET /health"
    """
    return exporter.get_finished_spans()


def clear_recorded_spans(exporter: "InMemorySpanExporter") -> None:
    """
    Clear all recorded spans from the exporter.

    Useful for resetting span state between test phases.

    Args:
        exporter: InMemorySpanExporter to clear
    """
    exporter.clear()


def assert_span_status(
    span: "ReadableSpan",
    expected_status: StatusCode,
    *,
    check_exception: bool = False,
) -> None:
    """
    Assert span status and optionally verify exception event.

    Helper for consistent span status assertions across tests.

    Args:
        span: ReadableSpan to check
        expected_status: Expected StatusCode (OK or ERROR)
        check_exception: If True, verify exception event exists when status is ERROR

    Example:
        >>> span = spans[0]
        >>> assert_span_status(span, StatusCode.OK)
        >>> assert_span_status(span, StatusCode.ERROR, check_exception=True)
    """
    assert span.status.status_code == expected_status, (
        f"Expected span status {expected_status}, got {span.status.status_code}"
    )

    if check_exception and expected_status == StatusCode.ERROR:
        exception_events = [e for e in span.events if e.name == "exception"]
        assert len(exception_events) >= 1, "Expected exception event in ERROR span"
