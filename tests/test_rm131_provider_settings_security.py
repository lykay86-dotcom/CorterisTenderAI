"""RM-131 no-secret, endpoint and no-startup-network guards."""

from __future__ import annotations

import json

from app.tenders.collector.provider_control import CollectorProviderManager
from app.tenders.collector.provider_settings import (
    ProviderConfiguration,
    ProviderSettingOrigin,
)


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
