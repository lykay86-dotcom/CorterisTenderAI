"""Tests for provider contracts and built-in placeholders."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.tenders.provider_base import (
    ProviderHealthStatus,
    ProviderNotConfiguredError,
    TenderSearchQuery,
)
from app.tenders.providers.placeholders import (
    create_builtin_providers,
)


def test_placeholder_health_reports_not_configured() -> None:
    provider = create_builtin_providers()[0]

    health = provider.check_health()

    assert health.provider_id == "eis"
    assert health.status == ProviderHealthStatus.NOT_CONFIGURED
    assert provider.validate_configuration()


def test_placeholder_search_fails_explicitly_until_connector_exists() -> None:
    provider = create_builtin_providers()[0]

    with pytest.raises(ProviderNotConfiguredError):
        provider.search(
            TenderSearchQuery(
                keywords=("видеонаблюдение", "СКУД"),
                page_size=25,
            )
        )


def test_search_query_validates_ranges() -> None:
    with pytest.raises(ValueError):
        TenderSearchQuery(min_price=100, max_price=10)

    with pytest.raises(ValueError):
        TenderSearchQuery(page=0)

    query = TenderSearchQuery(
        keywords=("шлагбаум",),
        regions=("Москва",),
        page=2,
        page_size=100,
    )
    assert query.page == 2
    assert query.page_size == 100


def test_search_query_normalizes_legacy_price_inputs_to_decimal() -> None:
    query = TenderSearchQuery(
        min_price=0.1,
        max_price="9007199254740993.01",
    )

    assert query.min_price == Decimal("0.1")
    assert query.max_price == Decimal("9007199254740993.01")
    assert query.price_currency == "RUB"

    usd_query = TenderSearchQuery(
        min_price=1,
        price_currency="usd",
    )
    assert usd_query.price_currency == "USD"

    for invalid in ("NaN", "Infinity", -1):
        with pytest.raises(ValueError):
            TenderSearchQuery(min_price=invalid)

    with pytest.raises(ValueError):
        TenderSearchQuery(price_currency="unknown")
