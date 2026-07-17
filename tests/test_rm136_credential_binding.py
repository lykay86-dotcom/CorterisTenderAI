"""RM-136 dynamic manual credential descriptors and runtime-only resolution."""

from app.tenders.provider_credentials import (
    ProviderCredentialService,
    manual_credential_descriptors,
)


MANUAL_ID = f"manual_{'4' * 32}"
SENTINEL = "RM136_RUNTIME_SECRET_SENTINEL"


class RuntimeBackend:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def has(self, name: str) -> bool:
        return name in self.values

    def save(self, name: str, value: str) -> None:
        self.values[name] = value

    def delete(self, name: str) -> None:
        self.values.pop(name, None)

    def get(self, name: str) -> str | None:
        return self.values.get(name)


def test_manual_descriptors_are_deterministic_nonsecret_and_allowlisted() -> None:
    descriptors = manual_credential_descriptors(MANUAL_ID, ("username", "password"))
    assert tuple(item.secret_name for item in descriptors) == ("username", "password")
    assert all(item.environment_name is None for item in descriptors)
    assert len({item.fingerprint for item in descriptors}) == 2


def test_runtime_secret_is_repr_redacted_and_marker_never_hashes_value() -> None:
    backend = RuntimeBackend()
    descriptors = manual_credential_descriptors(MANUAL_ID, ("api_key",))
    service = ProviderCredentialService(backend, environment={}, descriptors=descriptors)
    service.save_secret(MANUAL_ID, "api_key", SENTINEL)

    resolved = service.resolve_runtime_secret(MANUAL_ID, "api_key")
    marker = service.credential_marker(MANUAL_ID, ("api_key",))

    assert resolved.value == SENTINEL
    assert SENTINEL not in repr(resolved)
    assert SENTINEL not in marker
