"""RM-136 bounded read-only HTTP/RSS response validation."""

import asyncio

import pytest

from app.tenders.collector.cancellation import CollectorCancellationToken
from app.tenders.collector.manual_probe_transport import (
    ManualProviderProbeTransport,
    ManualProbeResponse,
    ManualProbeTransportError,
    validate_http_probe_response,
)
from app.tenders.collector.manual_provider_protocol import ManualProviderPayloadFormat
from app.tenders.collector.manual_provider_protocol import ManualProviderProtocolFamily


class _Resolver:
    async def resolve(self, hostname: str) -> tuple[str, ...]:
        assert hostname == "source.example.test"
        return ("93.184.216.34",)


class _Http:
    def __init__(self) -> None:
        self.pinned: list[str] = []

    async def get(self, target, pinned_address, cancellation_token, credentials):
        self.pinned.append(pinned_address)
        return ManualProbeResponse(200, "application/json", b'{"items": []}')


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


def test_orchestrator_passes_only_validated_pinned_address_to_get_port() -> None:
    http = _Http()
    transport = ManualProviderProbeTransport(resolver=_Resolver(), http=http)
    payload = asyncio.run(
        transport.probe_http(
            "https://source.example.test/feed",
            ManualProviderProtocolFamily.API,
            ManualProviderPayloadFormat.JSON,
            CollectorCancellationToken(),
        )
    )
    assert payload == b'{"items": []}'
    assert http.pinned == ["93.184.216.34"]


def test_cancellation_interrupts_inflight_resolution() -> None:
    class _SlowResolver:
        async def resolve(self, hostname: str) -> tuple[str, ...]:
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

    async def execute() -> None:
        token = CollectorCancellationToken()
        transport = ManualProviderProbeTransport(resolver=_SlowResolver(), http=_Http())
        task = asyncio.create_task(
            transport.probe_http(
                "https://source.example.test/feed",
                ManualProviderProtocolFamily.API,
                ManualProviderPayloadFormat.JSON,
                token,
            )
        )
        await asyncio.sleep(0)
        token.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=1)

    asyncio.run(execute())
