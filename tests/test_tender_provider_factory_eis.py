"""Tests for replacing the EIS placeholder with the real connector."""

from __future__ import annotations

from app.tenders.http_client import HttpResponse
from app.tenders.provider_factory import create_default_provider_registry
from app.tenders.providers.eis import EisTenderProvider
from app.tenders.providers.placeholders import PlaceholderTenderProvider


class NoNetworkTransport:
    def get(self, url, *, headers=None, timeout_seconds=20.0):
        return HttpResponse(
            url=url,
            status_code=200,
            headers={"content-type": "text/html; charset=utf-8"},
            body=b"<html></html>",
        )


def test_default_registry_uses_real_eis_and_keeps_other_placeholders() -> None:
    registry = create_default_provider_registry(http_transport=NoNetworkTransport())

    assert isinstance(registry.get("eis"), EisTenderProvider)
    assert isinstance(registry.get("sber_a"), PlaceholderTenderProvider)
    assert [item.id for item in registry.list_registered()][:3] == [
        "eis",
        "sber_a",
        "rts_tender",
    ]
