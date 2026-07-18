"""Regression baseline before the asynchronous collector is introduced."""

from __future__ import annotations

from decimal import Decimal
import json

from app.core.json_serialization import json_dumps
from app.tenders.collector import (
    COLLECTOR_ARCHITECTURE_VERSION,
    build_collector_baseline,
)
from app.tenders.http_client import HttpResponse
from app.tenders.models import TenderMoney
from app.tenders.provider_factory import create_default_provider_registry
from app.tenders.search_runtime import create_tender_search_runtime


class NoNetworkTransport:
    """Deterministic transport; runtime creation must not call it."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def get(
        self,
        url: str,
        *,
        headers=None,
        timeout_seconds: float = 20.0,
    ) -> HttpResponse:
        del headers, timeout_seconds
        self.calls.append(url)
        return HttpResponse(
            url=url,
            status_code=200,
            headers={"content-type": "text/html; charset=utf-8"},
            body=b"<html></html>",
        )


def test_collector_namespace_is_side_effect_free() -> None:
    assert COLLECTOR_ARCHITECTURE_VERSION == 1


def test_baseline_distinguishes_real_eis_from_placeholders() -> None:
    registry = create_default_provider_registry(http_transport=NoNetworkTransport())

    baseline = build_collector_baseline(registry)

    assert baseline.provider_ids[:3] == (
        "eis",
        "sber_a",
        "rts_tender",
    )
    assert baseline.implemented_provider_ids == ("eis",)
    assert "b2b_center" in baseline.placeholder_provider_ids
    eis = baseline.providers[0]
    assert eis.implementation_status == "public_html"
    assert eis.supports_search
    assert eis.supports_documents


def test_runtime_baseline_builds_without_network_activity(tmp_path) -> None:
    transport = NoNetworkTransport()
    runtime = create_tender_search_runtime(
        tmp_path,
        http_transport=transport,
    )

    baseline = build_collector_baseline(
        runtime.registry,
        runtime=runtime,
    )

    assert transport.calls == []
    assert not baseline.has_search_engine
    assert baseline.has_tender_registry
    assert baseline.has_document_store
    assert baseline.has_text_extraction
    assert baseline.has_requirement_analysis


def test_financial_json_precision_is_preserved() -> None:
    money = TenderMoney(amount=Decimal("1234567890.123456789"))

    payload = json.loads(json_dumps({"amount": money.amount}))

    assert payload["amount"] == "1234567890.123456789"
