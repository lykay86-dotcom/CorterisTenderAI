"""RM-132 canonical provider credential identity guards."""

from __future__ import annotations

import pytest

from app.tenders.provider_credentials import (
    CredentialDescriptor,
    CredentialState,
    ProviderCredentialService,
    provider_credential_descriptors,
)


class EmptyBackend:
    def has(self, _name: str) -> bool:
        return False

    def save(self, _name: str, _value: str) -> None:
        raise AssertionError("save not expected")

    def delete(self, _name: str) -> None:
        return None


def test_descriptor_registry_uses_only_existing_canonical_names() -> None:
    descriptors = provider_credential_descriptors()

    assert tuple(item.provider_id for item in descriptors) == (
        "mos_supplier",
        "b2b_center",
        "gazprombank",
        "fabrikant",
        "tek_torg",
        "otc",
        "sber_commercial",
        "rts_commercial",
        "roseltorg_commercial",
    )
    assert {item.secret_name for item in descriptors} == {"api_key"}
    assert len({item.keyring_name for item in descriptors}) == len(descriptors)
    assert len({item.environment_variable for item in descriptors}) == len(descriptors)
    assert all(item.keyring_name == f"collector.{item.provider_id}.api_key" for item in descriptors)


@pytest.mark.parametrize(
    ("alias", "canonical"),
    [
        ("sber_a", "sber_commercial"),
        ("rts_tender", "rts_commercial"),
        ("roseltorg", "roseltorg_commercial"),
    ],
)
def test_only_audited_aliases_resolve(alias: str, canonical: str) -> None:
    service = ProviderCredentialService(EmptyBackend(), environment={})

    state = service.has_secret(alias, "api_key")

    assert state.provider_id == canonical
    assert state.state is CredentialState.NOT_CONFIGURED


def test_ambiguous_or_noncredential_provider_fails_closed() -> None:
    service = ProviderCredentialService(EmptyBackend(), environment={})

    assert service.has_secret("commercial", "api_key").state is CredentialState.INVALID_REQUEST
    assert service.has_secret("eis", "api_key").state is CredentialState.INVALID_REQUEST


def test_duplicate_account_or_alias_mapping_is_rejected() -> None:
    duplicate = (
        CredentialDescriptor("b2b_center", "api_key", "shared", "ENV_A"),
        CredentialDescriptor("gazprombank", "api_key", "shared", "ENV_B"),
    )

    with pytest.raises(ValueError, match="unique"):
        ProviderCredentialService(EmptyBackend(), environment={}, descriptors=duplicate)
