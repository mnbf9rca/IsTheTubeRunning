"""OpenTelemetry test helper functions."""

from typing import TYPE_CHECKING

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
