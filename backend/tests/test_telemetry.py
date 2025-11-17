"""Tests for OpenTelemetry telemetry module."""

import threading

import pytest
from app.core import telemetry
from app.core.config import settings
from opentelemetry.sdk.trace import TracerProvider


def test_get_tracer_provider_returns_none_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that get_tracer_provider returns None when OTEL is disabled."""
    monkeypatch.setattr(settings, "OTEL_ENABLED", False)
    telemetry._tracer_provider = None

    provider = telemetry.get_tracer_provider()

    assert provider is None


def test_get_tracer_provider_lazy_initialization(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that TracerProvider is created lazily on first access."""
    monkeypatch.setattr(settings, "OTEL_ENABLED", True)
    monkeypatch.setattr(settings, "DEBUG", True)  # Skip endpoint validation
    monkeypatch.setattr(settings, "OTEL_EXPORTER_OTLP_ENDPOINT", None)

    # Initially None
    telemetry._tracer_provider = None
    assert telemetry._tracer_provider is None

    # Created on first call
    provider = telemetry.get_tracer_provider()
    assert provider is not None
    assert isinstance(provider, TracerProvider)
    assert telemetry._tracer_provider is provider


def test_get_tracer_provider_singleton_pattern(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that multiple calls return the same TracerProvider instance."""
    monkeypatch.setattr(settings, "OTEL_ENABLED", True)
    monkeypatch.setattr(settings, "DEBUG", True)
    monkeypatch.setattr(settings, "OTEL_EXPORTER_OTLP_ENDPOINT", None)
    telemetry._tracer_provider = None

    provider1 = telemetry.get_tracer_provider()
    provider2 = telemetry.get_tracer_provider()

    assert provider1 is provider2


def test_get_tracer_provider_thread_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that TracerProvider initialization is thread-safe."""
    monkeypatch.setattr(settings, "OTEL_ENABLED", True)
    monkeypatch.setattr(settings, "DEBUG", True)
    monkeypatch.setattr(settings, "OTEL_EXPORTER_OTLP_ENDPOINT", None)
    telemetry._tracer_provider = None

    providers: list[TracerProvider | None] = []

    def get_provider() -> None:
        providers.append(telemetry.get_tracer_provider())

    # Create multiple threads that try to get provider simultaneously
    threads = [threading.Thread(target=get_provider) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # All threads should get the same instance
    assert all(p is providers[0] for p in providers)


def test_create_tracer_provider_requires_endpoint_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that TracerProvider requires OTLP endpoint in production mode."""
    monkeypatch.setattr(settings, "OTEL_ENABLED", True)
    monkeypatch.setattr(settings, "DEBUG", False)  # Production mode
    monkeypatch.setattr(settings, "OTEL_EXPORTER_OTLP_ENDPOINT", None)
    telemetry._tracer_provider = None

    with pytest.raises(ValueError, match=r"Required configuration missing.*OTEL_EXPORTER_OTLP_ENDPOINT"):
        telemetry.get_tracer_provider()


def test_create_tracer_provider_with_otlp_exporter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test TracerProvider creation with OTLP exporter configured."""
    monkeypatch.setattr(settings, "OTEL_ENABLED", True)
    monkeypatch.setattr(settings, "DEBUG", False)
    monkeypatch.setattr(settings, "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318/v1/traces")
    monkeypatch.setattr(settings, "OTEL_EXPORTER_OTLP_HEADERS", "Authorization=Bearer token123")
    monkeypatch.setattr(settings, "OTEL_ENVIRONMENT", "production")
    telemetry._tracer_provider = None

    provider = telemetry.get_tracer_provider()

    assert provider is not None
    assert isinstance(provider, TracerProvider)

    # Verify resource attributes
    resource = provider.resource
    assert resource.attributes["service.name"] == "isthetuberunning-backend"
    assert resource.attributes["deployment.environment"] == "production"
    assert "service.version" in resource.attributes


def test_parse_otlp_headers_empty_string() -> None:
    """Test parsing empty OTLP headers string."""
    headers = telemetry._parse_otlp_headers("")
    assert headers == {}


def test_parse_otlp_headers_single_pair() -> None:
    """Test parsing single OTLP header pair."""
    headers = telemetry._parse_otlp_headers("Authorization=Bearer token123")
    assert headers == {"Authorization": "Bearer token123"}


def test_parse_otlp_headers_multiple_pairs() -> None:
    """Test parsing multiple OTLP header pairs."""
    headers = telemetry._parse_otlp_headers("Authorization=Bearer token123,X-Custom=value,X-Another=test")
    assert headers == {
        "Authorization": "Bearer token123",
        "X-Custom": "value",
        "X-Another": "test",
    }


def test_parse_otlp_headers_with_whitespace() -> None:
    """Test parsing OTLP headers with extra whitespace."""
    headers = telemetry._parse_otlp_headers("  Authorization = Bearer token123 , X-Custom = value  ")
    assert headers == {
        "Authorization": "Bearer token123",
        "X-Custom": "value",
    }


def test_parse_otlp_headers_ignores_invalid_pairs(caplog: pytest.LogCaptureFixture) -> None:
    """Test that invalid header pairs (no equals sign) are ignored with warning."""
    headers = telemetry._parse_otlp_headers("ValidHeader=value,InvalidHeader,AnotherValid=test")
    assert headers == {
        "ValidHeader": "value",
        "AnotherValid": "test",
    }
    # Verify warning was logged
    assert any("Malformed OTLP header pair ignored: 'InvalidHeader'" in record.message for record in caplog.records)


def test_parse_otlp_headers_multiple_equals_signs() -> None:
    """Test that header values containing equals signs are handled correctly."""
    # Authorization headers often have = in the value (e.g., Base64-encoded tokens)
    headers = telemetry._parse_otlp_headers("Authorization=Basic dXNlcjpwYXNz,Token=abc=123=xyz")
    assert headers == {
        "Authorization": "Basic dXNlcjpwYXNz",
        "Token": "abc=123=xyz",
    }


def test_parse_otlp_headers_empty_key_or_value() -> None:
    """Test that empty keys or values are preserved (edge case)."""
    # Empty value after equals sign
    headers = telemetry._parse_otlp_headers("EmptyValue=")
    assert headers == {"EmptyValue": ""}

    # Empty key before equals sign (unusual but valid syntax)
    headers = telemetry._parse_otlp_headers("=SomeValue")
    assert headers == {"": "SomeValue"}


def test_shutdown_tracer_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test graceful shutdown of TracerProvider."""
    monkeypatch.setattr(settings, "OTEL_ENABLED", True)
    monkeypatch.setattr(settings, "DEBUG", True)
    monkeypatch.setattr(settings, "OTEL_EXPORTER_OTLP_ENDPOINT", None)
    telemetry._tracer_provider = None

    # Create provider
    provider = telemetry.get_tracer_provider()
    assert provider is not None

    # Shutdown should not raise
    telemetry.shutdown_tracer_provider()


def test_shutdown_tracer_provider_when_none() -> None:
    """Test that shutdown is safe to call when provider is None."""
    telemetry._tracer_provider = None

    # Should not raise
    telemetry.shutdown_tracer_provider()


def test_shutdown_tracer_provider_multiple_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that shutdown can be called multiple times safely."""
    monkeypatch.setattr(settings, "OTEL_ENABLED", True)
    monkeypatch.setattr(settings, "DEBUG", True)
    monkeypatch.setattr(settings, "OTEL_EXPORTER_OTLP_ENDPOINT", None)
    telemetry._tracer_provider = None

    provider = telemetry.get_tracer_provider()
    assert provider is not None

    # Multiple shutdowns should not raise
    telemetry.shutdown_tracer_provider()
    telemetry.shutdown_tracer_provider()


def test_get_current_span_when_no_span_active() -> None:
    """Test get_current_span returns None when no span is active."""
    span = telemetry.get_current_span()
    # In tests with OTEL_SDK_DISABLED, this should return a no-op span or None
    # We just verify it doesn't crash
    assert span is not None  # OTEL SDK returns a no-op span when disabled


def test_create_tracer_provider_without_endpoint_in_debug(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that TracerProvider can be created without endpoint in DEBUG mode."""
    monkeypatch.setattr(settings, "OTEL_ENABLED", True)
    monkeypatch.setattr(settings, "DEBUG", True)
    monkeypatch.setattr(settings, "OTEL_EXPORTER_OTLP_ENDPOINT", None)
    telemetry._tracer_provider = None

    provider = telemetry.get_tracer_provider()

    assert provider is not None
    assert isinstance(provider, TracerProvider)
    # Should log warning about no endpoint
    assert any("no OTLP endpoint configured" in record.message for record in caplog.records)
