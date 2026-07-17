"""RM-132 runtime environment override isolation."""

from __future__ import annotations

from app.tenders.provider_credentials import (
    CredentialCommandStatus,
    CredentialState,
    ProviderCredentialService,
)


class TrackingBackend:
    def __init__(self) -> None:
        self.has_calls: list[str] = []
        self.saves: list[tuple[str, str]] = []
        self.deletes: list[str] = []

    def has(self, name: str) -> bool:
        self.has_calls.append(name)
        return True

    def save(self, name: str, value: str) -> None:
        self.saves.append((name, value))

    def delete(self, name: str) -> None:
        self.deletes.append(name)


def test_environment_state_does_not_read_or_copy_value() -> None:
    sentinel = "RM132_SECRET_SENTINEL_ENVIRONMENT"
    backend = TrackingBackend()
    service = ProviderCredentialService(
        backend,
        environment={"CORTERIS_MOS_API_KEY": sentinel},
    )

    state = service.has_secret("mos_supplier", "api_key")
    save = service.save_secret("mos_supplier", "api_key", "new-value")

    assert state.state is CredentialState.ENVIRONMENT_OVERRIDE
    assert save.status is CredentialCommandStatus.ENVIRONMENT_OVERRIDE
    assert backend.has_calls == []
    assert backend.saves == []
    assert sentinel not in repr(state)
    assert sentinel not in repr(save)


def test_delete_protected_store_does_not_change_environment_state() -> None:
    backend = TrackingBackend()
    service = ProviderCredentialService(
        backend,
        environment={"CORTERIS_B2B_API_KEY": "runtime-only"},
    )

    deleted = service.delete_secret("b2b_center", "api_key")
    state = service.has_secret("b2b_center", "api_key")

    assert deleted.status is CredentialCommandStatus.DELETED
    assert deleted.state is CredentialState.ENVIRONMENT_OVERRIDE
    assert state.state is CredentialState.ENVIRONMENT_OVERRIDE
    assert backend.deletes == ["collector.b2b_center.api_key"]
    assert backend.has_calls == []
