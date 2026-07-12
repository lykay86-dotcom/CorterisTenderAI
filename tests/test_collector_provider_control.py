"""Tests for provider states and persisted health diagnostics."""

from __future__ import annotations

from app.tenders.collector.provider_control import (
    CollectorProviderManager,
    ProviderCheckRepository,
    ProviderUiState,
)
from app.tenders.provider_base import (
    ProviderHealth,
    ProviderHealthStatus,
)


async def fake_checker(provider_ids):
    return {
        provider_id: ProviderHealth(
            provider_id=provider_id,
            status=(
                ProviderHealthStatus.AVAILABLE
                if provider_id == "eis"
                else ProviderHealthStatus.NOT_CONFIGURED
            ),
            checked_at="2026-07-12T12:00:00+00:00",
            message=(
                "ЕИС отвечает"
                if provider_id == "eis"
                else "Требуется bearer-токен"
            ),
            latency_ms=125,
        )
        for provider_id in provider_ids
    }


def test_manager_exposes_all_sources_without_network(tmp_path) -> None:
    manager = CollectorProviderManager(
        tmp_path,
        environment={},
    )

    states = {
        item.provider_id: item
        for item in manager.states()
    }

    assert states["eis"].enabled
    assert states["eis"].ui_state == ProviderUiState.LIMITED
    assert states["mos_supplier"].ui_state == (
        ProviderUiState.NOT_CONFIGURED
    )
    assert not states["b2b_center"].enabled
    assert states["b2b_center"].ui_state == (
        ProviderUiState.DISABLED
    )
    assert len(states) == 10


def test_manager_persists_switch_and_commercial_switch(
    tmp_path,
) -> None:
    manager = CollectorProviderManager(
        tmp_path,
        environment={},
    )

    state = manager.set_enabled("b2b_center", True)

    assert state.enabled
    assert state.ui_state == ProviderUiState.NOT_CONFIGURED
    commercial = (
        manager.commercial_settings_repository.load()
    )
    assert commercial["b2b_center"].enabled


def test_health_check_persists_success_and_error(tmp_path) -> None:
    manager = CollectorProviderManager(
        tmp_path,
        environment={},
        health_checker=fake_checker,
    )

    states = __import__("asyncio").run(
        manager.check_providers(
            ("eis", "mos_supplier")
        )
    )
    by_id = {item.provider_id: item for item in states}

    assert by_id["eis"].ui_state == ProviderUiState.UNVERIFIED
    assert by_id["eis"].last_success_at == (
        "2026-07-12T12:00:00+00:00"
    )
    assert by_id["mos_supplier"].ui_state == (
        ProviderUiState.NOT_CONFIGURED
    )
    records = ProviderCheckRepository(
        tmp_path / "collector_provider_health.json"
    ).load()
    assert records["eis"].latency_ms == 125
