"""RM-131 no-secret, endpoint and no-startup-network guards."""

from __future__ import annotations

import asyncio
import json

import pytest

from app.tenders.collector.provider_control import (
    CollectorProviderManager,
    ProviderUiState,
)
from app.tenders.collector.provider_settings import (
    ProviderConfiguration,
    ProviderSettingOrigin,
    ProviderSettingsMutationError,
)
from app.tenders.collector.run_session import CollectorRunSession
from app.tenders.provider_base import TenderSearchQuery


def test_environment_override_is_runtime_only_and_secret_free(tmp_path) -> None:
    secret = "rm131-super-secret-token"
    manager = CollectorProviderManager(
        tmp_path,
        environment={
            "CORTERIS_B2B_ENABLED": "true",
            "CORTERIS_B2B_ACCESS_CONFIRMED": "true",
            "CORTERIS_B2B_API_BASE_URL": "https://env.example.test/v1",
            "CORTERIS_B2B_API_KEY": secret,
        },
    )
    snapshot = manager.settings_snapshot()
    b2b = snapshot.get("b2b_center")

    assert b2b.enabled is True
    assert b2b.enabled_origin is ProviderSettingOrigin.ENVIRONMENT
    assert b2b.configuration_origin is ProviderSettingOrigin.ENVIRONMENT
    assert secret not in repr(snapshot)
    assert secret not in json.dumps(snapshot.public_payload(), ensure_ascii=False)
    assert not (tmp_path / "collector_provider_settings.json").exists()


def test_persisted_payload_cannot_contain_secret_or_unsafe_endpoint(tmp_path) -> None:
    manager = CollectorProviderManager(tmp_path, environment={})
    manager.set_enabled("b2b_center", True)
    manager.set_configuration(
        "b2b_center",
        ProviderConfiguration(
            access_confirmed=True,
            api_base_url="https://api.example.test/v1",
        ),
    )

    text = (tmp_path / "collector_provider_settings.json").read_text(encoding="utf-8")
    lowered = text.casefold()

    for forbidden in ("api_key", "token", "password", "username", "masked", "last_error"):
        assert forbidden not in lowered
    assert "?" not in text
    assert "#" not in text
    assert "@" not in text


def test_manager_snapshot_and_states_do_not_start_network(tmp_path, monkeypatch) -> None:
    def fail_network():
        raise AssertionError("startup network is forbidden")

    monkeypatch.setattr(
        "app.tenders.collector.provider_control.create_collector_network_runtime",
        fail_network,
    )
    manager = CollectorProviderManager(tmp_path, environment={})

    assert manager.settings_snapshot().get("eis").enabled
    assert manager.states()


def test_corrupt_settings_block_states_and_run_before_runtime(tmp_path) -> None:
    (tmp_path / "collector_provider_settings.json").write_text("{broken", encoding="utf-8")
    manager = CollectorProviderManager(tmp_path, environment={})
    states = manager.states()
    runtime_calls = 0

    def runtime_factory():
        nonlocal runtime_calls
        runtime_calls += 1
        raise AssertionError("runtime must not be created")

    session = CollectorRunSession(
        tmp_path,
        runtime_factory=runtime_factory,
        provider_settings_snapshot_factory=manager.settings_snapshot,
    )

    assert all(not state.enabled for state in states)
    assert all(state.ui_state is ProviderUiState.ERROR for state in states)
    assert all(not state.enabled_editable for state in states)
    with pytest.raises(ProviderSettingsMutationError, match="corrupt"):
        asyncio.run(session.run(TenderSearchQuery(), provider_ids=("eis",)))
    assert runtime_calls == 0
