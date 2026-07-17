from __future__ import annotations

import json

from app.tenders.providers.commercial_catalog import (
    CommercialProviderSettingsRepository,
    CommercialProviderState,
    CommercialProviderUserSettings,
    create_commercial_provider_catalog,
    default_commercial_provider_definitions,
)


def test_default_catalog_contains_all_planned_commercial_sources() -> None:
    definitions = default_commercial_provider_definitions()

    assert [item.provider_id for item in definitions] == [
        "b2b_center",
        "gazprombank",
        "fabrikant",
        "tek_torg",
        "otc",
        "sber_commercial",
        "rts_commercial",
        "roseltorg_commercial",
    ]
    assert all(not item.descriptor.enabled_by_default for item in definitions)
    assert all(
        item.descriptor.implementation_status == "commercial_access_pending" for item in definitions
    )


def test_catalog_is_disabled_by_default_and_never_claims_working() -> None:
    catalog = create_commercial_provider_catalog(environment={})
    resolved = catalog.resolve_all()

    assert len(resolved) == 8
    assert all(item.state == CommercialProviderState.DISABLED for item in resolved)
    assert all(not item.is_working for item in resolved)


def test_explicit_environment_does_not_read_host_keyring(monkeypatch) -> None:
    requested_names: list[str] = []
    monkeypatch.setattr(
        "app.tenders.providers.commercial_catalog._load_keyring_secret_safely",
        lambda name: requested_names.append(name) or "host-secret",
    )

    catalog = create_commercial_provider_catalog(environment={})

    assert catalog.resolve_all()
    assert requested_names == []
    assert all(not item.api_key for item in catalog.resolve_all())


def test_readiness_progresses_without_marking_provider_available() -> None:
    base = {
        "CORTERIS_B2B_ENABLED": "true",
    }
    assert (
        create_commercial_provider_catalog(environment=base).get("b2b_center").state
        == CommercialProviderState.CONTRACT_REQUIRED
    )

    with_contract = {
        **base,
        "CORTERIS_B2B_ACCESS_CONFIRMED": "true",
    }
    assert (
        create_commercial_provider_catalog(environment=with_contract).get("b2b_center").state
        == CommercialProviderState.CREDENTIALS_REQUIRED
    )

    with_key = {
        **with_contract,
        "CORTERIS_B2B_API_KEY": "secret-value-123456",
    }
    assert (
        create_commercial_provider_catalog(environment=with_key).get("b2b_center").state
        == CommercialProviderState.ENDPOINT_REQUIRED
    )

    ready = {
        **with_key,
        "CORTERIS_B2B_API_BASE_URL": "https://api.example.test/",
    }
    settings = create_commercial_provider_catalog(environment=ready).get("b2b_center")

    assert settings.state == CommercialProviderState.READY_FOR_VERIFICATION
    assert not settings.is_working
    assert not hasattr(settings, "masked_api_key")
    assert "masked_api_key" not in settings.public_payload()
    assert "secret-value-123456" not in repr(settings)
    assert "secret-value-123456" not in json.dumps(
        settings.public_payload(),
        ensure_ascii=False,
    )


def test_non_secret_settings_repository_roundtrip(tmp_path) -> None:
    path = tmp_path / "commercial_providers.json"
    repository = CommercialProviderSettingsRepository(path)
    repository.update(
        "b2b_center",
        CommercialProviderUserSettings(
            enabled=True,
            access_confirmed=True,
            api_base_url="https://api.example.test/",
        ),
    )

    loaded = repository.load()

    assert loaded["b2b_center"].enabled
    assert loaded["b2b_center"].access_confirmed
    assert loaded["b2b_center"].api_base_url == "https://api.example.test"
    raw = path.read_text(encoding="utf-8")
    assert "api_key" not in raw
    assert "password" not in raw

    repository.update(
        "b2b_center",
        CommercialProviderUserSettings(
            enabled=True,
            access_confirmed=True,
            api_base_url=("https://user:password@api.example.test/v1?token=secret"),
        ),
    )
    sanitized = repository.load()["b2b_center"]
    assert sanitized.api_base_url == ""
    assert "secret" not in path.read_text(encoding="utf-8")
