"""RM-136 bounded read-only HTTP/RSS response validation."""

import pytest

from app.tenders.collector.manual_probe_transport import (
    ManualProbeResponse,
    ManualProbeTransportError,
    validate_http_probe_response,
)
from app.tenders.collector.manual_provider_protocol import ManualProviderPayloadFormat


def test_json_and_rss_validation_returns_only_bounded_payload() -> None:
    json_response = ManualProbeResponse(
        status_code=200,
        content_type="application/json",
        body=b'{"items": []}',
    )
    rss_response = ManualProbeResponse(
        status_code=200,
        content_type="application/rss+xml",
        body=b"<rss><channel /></rss>",
    )
    assert validate_http_probe_response(json_response, ManualProviderPayloadFormat.JSON).startswith(
        b"{"
    )
    assert validate_http_probe_response(rss_response, ManualProviderPayloadFormat.RSS).startswith(
        b"<rss"
    )


def test_response_validation_rejects_redirect_error_mime_and_oversize() -> None:
    for response, payload_format in (
        (ManualProbeResponse(302, "application/json", b"{}"), ManualProviderPayloadFormat.JSON),
        (ManualProbeResponse(200, "text/html", b"<html />"), ManualProviderPayloadFormat.JSON),
        (
            ManualProbeResponse(200, "application/json", b"x" * 1025),
            ManualProviderPayloadFormat.JSON,
        ),
    ):
        with pytest.raises(ManualProbeTransportError):
            validate_http_probe_response(response, payload_format, max_body_bytes=1024)
