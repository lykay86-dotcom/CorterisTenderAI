from __future__ import annotations

from app.tenders.collector.network_settings import (
    default_collector_network_settings,
)


def test_network_settings_cover_all_planned_commercial_providers() -> None:
    settings = default_collector_network_settings()

    for provider_id in (
        "zakaz_rf",
        "roseltorg",
        "rad",
        "tek_torg",
        "ets_nep",
        "sber_a",
        "rts_tender",
        "gazprombank",
        "b2b_center",
        "fabrikant",
        "otc",
    ):
        provider = settings.get(provider_id)
        assert provider.provider_id == provider_id
        assert provider.domains
        assert provider.rate_limit.max_concurrent >= 1
