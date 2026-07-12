from __future__ import annotations

from app.tenders.collector.network_settings import (
    default_collector_network_settings,
)


def test_default_network_settings_are_conservative() -> None:
    settings = default_collector_network_settings()
    eis = settings.get("eis")
    mos = settings.get("mos_supplier")

    assert eis.timeouts.connect_seconds == 20
    assert eis.rate_limit.max_concurrent == 1
    assert eis.rate_limit.requests_per_second == 0.5
    assert eis.retry.max_attempts == 3
    assert mos.domains == (
        "api.zakupki.mos.ru",
        "zakupki.mos.ru",
    )
    assert mos.rate_limit.max_concurrent == 1
    assert settings.domain_rate_limits["zakupki.gov.ru"] is eis.rate_limit
    assert (
        settings.domain_rate_limits["api.zakupki.mos.ru"]
        is mos.rate_limit
    )
