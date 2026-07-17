"""RM-132 protected credential command contract."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime

from app.tenders.provider_credentials import (
    CredentialCommandStatus,
    CredentialErrorCategory,
    CredentialState,
    ProviderCredentialService,
)


class FakeCredentialBackend:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.saves: list[tuple[str, str]] = []
        self.deletes: list[str] = []

    def has(self, name: str) -> bool:
        return name in self.values

    def save(self, name: str, value: str) -> None:
        self.saves.append((name, value))
        self.values[name] = value

    def delete(self, name: str) -> None:
        self.deletes.append(name)
        self.values.pop(name, None)


def test_save_replace_and_idempotent_delete_never_return_value() -> None:
    backend = FakeCredentialBackend()
    service = ProviderCredentialService(backend, environment={})

    missing = service.has_secret("mos_supplier", "api_key")
    saved = service.save_secret("mos_supplier", "api_key", "  exact value  ")
    configured = service.has_secret("mos_supplier", "api_key")
    refused = service.save_secret("mos_supplier", "api_key", "second")
    replaced = service.save_secret(
        "mos_supplier",
        "api_key",
        " replacement with spaces ",
        replace=True,
    )
    deleted = service.delete_secret("mos_supplier", "api_key")
    repeated = service.delete_secret("mos_supplier", "api_key")

    assert missing.state is CredentialState.NOT_CONFIGURED
    assert saved.status is CredentialCommandStatus.SAVED
    assert configured.state is CredentialState.CONFIGURED
    assert refused.status is CredentialCommandStatus.REPLACEMENT_REQUIRED
    assert replaced.status is CredentialCommandStatus.REPLACED
    assert deleted.status is CredentialCommandStatus.DELETED
    assert repeated.status is CredentialCommandStatus.ALREADY_MISSING
    assert backend.saves == [
        ("collector.mos_supplier.api_key", "  exact value  "),
        ("collector.mos_supplier.api_key", " replacement with spaces "),
    ]
    assert not hasattr(saved, "value")
    assert "replacement with spaces" not in repr(replaced)


def test_invalid_values_fail_before_backend_access() -> None:
    backend = FakeCredentialBackend()
    service = ProviderCredentialService(backend, environment={})

    for value in ("", "   ", "line\nbreak", "control\x7fvalue"):
        result = service.save_secret("mos_supplier", "api_key", value)
        assert result.status is CredentialCommandStatus.INVALID_INPUT
        assert result.error_category is CredentialErrorCategory.INVALID_INPUT

    unknown = service.save_secret("unknown", "api_key", "value")
    arbitrary = service.save_secret("mos_supplier", "password", "value")

    assert unknown.status is CredentialCommandStatus.INVALID_INPUT
    assert arbitrary.status is CredentialCommandStatus.INVALID_INPUT
    assert backend.saves == []


def test_result_timestamp_is_aware_and_serialization_is_secret_free() -> None:
    sentinel = "RM132_SECRET_SENTINEL_SERVICE"
    service = ProviderCredentialService(FakeCredentialBackend(), environment={})

    result = service.save_secret("b2b_center", "api_key", sentinel)
    payload = asdict(result)

    observed = datetime.fromisoformat(result.observed_at)
    assert observed.tzinfo is not None
    assert sentinel not in repr(result)
    assert sentinel not in repr(payload)
    assert set(payload) == {
        "provider_id",
        "secret_name",
        "status",
        "state",
        "error_category",
        "message",
        "observed_at",
    }
