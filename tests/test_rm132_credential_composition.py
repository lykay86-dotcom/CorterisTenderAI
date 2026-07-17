"""RM-132 manager and startup composition guards."""

from __future__ import annotations

from app.tenders.collector.provider_control import CollectorProviderManager
from app.tenders.provider_credentials import CredentialState, ProviderCredentialService


class TripwireBackend:
    def __init__(self) -> None:
        self.has_calls = 0
        self.values: dict[str, str] = {}

    def has(self, name: str) -> bool:
        self.has_calls += 1
        return name in self.values

    def save(self, name: str, value: str) -> None:
        self.values[name] = value

    def delete(self, name: str) -> None:
        self.values.pop(name, None)


def test_ordinary_manager_states_do_not_read_keyring_or_start_network(
    tmp_path, monkeypatch
) -> None:
    backend = TripwireBackend()
    service = ProviderCredentialService(backend, environment={})
    monkeypatch.setattr(
        "app.tenders.collector.provider_control.create_collector_network_runtime",
        lambda: (_ for _ in ()).throw(AssertionError("network startup")),
    )
    manager = CollectorProviderManager(
        tmp_path,
        environment={},
        credential_service=service,
    )

    states = manager.states()

    assert states
    assert backend.has_calls == 0
    assert all(state.credential_state is None for state in states)


def test_explicit_safe_state_is_joined_without_value(tmp_path) -> None:
    backend = TripwireBackend()
    backend.values["collector.mos_supplier.api_key"] = "RM132_SECRET_SENTINEL_COMPOSITION"
    manager = CollectorProviderManager(
        tmp_path,
        environment={},
        credential_service=ProviderCredentialService(backend, environment={}),
    )

    safe = manager.credential_state("mos_supplier", "api_key")
    state = next(item for item in manager.states() if item.provider_id == "mos_supplier")

    assert safe.state is CredentialState.CONFIGURED
    assert state.credential_state is CredentialState.CONFIGURED
    assert "SENTINEL" not in repr(state)


def test_save_and_delete_do_not_modify_settings_or_sqlite(tmp_path) -> None:
    backend = TripwireBackend()
    manager = CollectorProviderManager(
        tmp_path,
        environment={},
        credential_service=ProviderCredentialService(backend, environment={}),
    )
    manager.set_enabled("mos_supplier", True)
    settings_path = tmp_path / "collector_provider_settings.json"
    before = settings_path.read_bytes()

    manager.save_credential("mos_supplier", "api_key", "credential")
    manager.delete_credential("mos_supplier", "api_key")

    assert settings_path.read_bytes() == before
    sqlite_path = tmp_path / "tender_registry.sqlite3"
    assert not sqlite_path.exists() or b"credential" not in sqlite_path.read_bytes()
