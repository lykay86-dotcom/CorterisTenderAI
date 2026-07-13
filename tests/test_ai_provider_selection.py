from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from app.ai.provider import DisabledProvider, OpenAICompatibleProvider
from app.core.ai.provider_selection import (
    AiProviderId,
    AiProviderSelectionService,
    AiProviderSettings,
    LegacyAiProviderSettings,
    OPENAI_API_KEY_SECRET,
    OPENAI_DEFAULT_BASE_URL,
)
from app.core.config_manager import ConfigManager


@dataclass
class SecretStore:
    value: str | None = None
    loads: list[str] = field(default_factory=list)
    saves: list[tuple[str, str]] = field(default_factory=list)
    fail_load: bool = False
    fail_save: bool = False

    def load(self, name: str) -> str | None:
        self.loads.append(name)
        if self.fail_load:
            raise AssertionError("private C:\\Users\\person\\secret.txt token=do-not-leak")
        return self.value

    def save(self, name: str, value: str) -> None:
        if self.fail_save:
            raise RuntimeError("api_key=do-not-leak")
        self.saves.append((name, value))
        self.value = value

    def delete(self, name: str) -> None:
        self.value = None


def _service(tmp_path, *, secret: SecretStore | None = None) -> AiProviderSelectionService:
    return AiProviderSelectionService(
        ConfigManager(tmp_path / "settings.json"),
        secret or SecretStore(),
    )


def _settings(
    provider_id: AiProviderId,
    *,
    model: str = "gpt-test",
    base_url: str = "https://ai.example.test/v1",
) -> AiProviderSettings:
    return AiProviderSettings(provider_id, model=model, base_url=base_url)


def test_disabled_returns_existing_provider_without_reading_secret(tmp_path) -> None:
    secret = SecretStore(fail_load=True)
    service = _service(tmp_path, secret=secret)
    service.config.set("ai.provider", "disabled")  # type: ignore[attr-defined]

    resolution = service.resolve_provider()

    assert isinstance(resolution.provider, DisabledProvider)
    assert resolution.effective_provider_id is AiProviderId.DISABLED
    assert resolution.available
    assert secret.loads == []


def test_unknown_id_degrades_without_echoing_raw_configuration(tmp_path) -> None:
    service = _service(tmp_path)
    service.config.set("ai.provider", "private-provider?token=do-not-leak")  # type: ignore[attr-defined]

    resolution = service.resolve_provider()

    assert isinstance(resolution.provider, DisabledProvider)
    assert not resolution.available
    assert "do-not-leak" not in repr(resolution)


def test_missing_secret_degrades_to_disabled(tmp_path) -> None:
    service = _service(tmp_path)
    service.config.set("ai.provider", "openai")  # type: ignore[attr-defined]

    resolution = service.resolve_provider()

    assert resolution.effective_provider_id is AiProviderId.DISABLED
    assert not resolution.available
    assert resolution.warnings


def test_secret_store_exception_is_sanitized(tmp_path, caplog) -> None:
    service = _service(tmp_path, secret=SecretStore(fail_load=True))
    service.config.set("ai.provider", "openai")  # type: ignore[attr-defined]

    resolution = service.resolve_provider()

    assert isinstance(resolution.provider, DisabledProvider)
    assert "do-not-leak" not in repr(resolution)
    assert "Users" not in repr(resolution)
    assert "do-not-leak" not in caplog.text


def test_openai_reuses_compatible_provider_and_official_url(tmp_path) -> None:
    service = _service(tmp_path, secret=SecretStore("secret-value"))
    service.config.update(  # type: ignore[attr-defined]
        {"ai": {"provider": "openai", "model": "gpt-test", "base_url": "https://ignored"}}
    )

    resolution = service.resolve_provider()

    assert isinstance(resolution.provider, OpenAICompatibleProvider)
    assert resolution.provider.base_url == OPENAI_DEFAULT_BASE_URL
    assert resolution.provider.model == "gpt-test"
    assert resolution.effective_provider_id is AiProviderId.OPENAI


def test_openai_compatible_reuses_existing_provider(tmp_path) -> None:
    service = _service(tmp_path, secret=SecretStore("secret-value"))
    service.config.update(  # type: ignore[attr-defined]
        {
            "ai": {
                "provider": "openai_compatible",
                "model": "custom-model",
                "base_url": "https://ai.example.test/v1/",
            }
        }
    )

    resolution = service.resolve_provider()

    assert isinstance(resolution.provider, OpenAICompatibleProvider)
    assert resolution.provider.base_url == "https://ai.example.test/v1"
    assert resolution.provider.model == "custom-model"


@pytest.mark.parametrize(
    "base_url",
    [
        "ftp://ai.example.test/v1",
        "https://user:password@ai.example.test/v1",
        "https://ai.example.test/v1#private",
        "https://",
        "not-a-url",
    ],
)
def test_invalid_compatible_url_falls_back_without_network(tmp_path, base_url: str) -> None:
    secret = SecretStore("secret-value")
    service = _service(tmp_path, secret=secret)
    service.config.update(  # type: ignore[attr-defined]
        {
            "ai": {
                "provider": "openai_compatible",
                "model": "custom-model",
                "base_url": base_url,
            }
        }
    )

    resolution = service.resolve_provider()

    assert isinstance(resolution.provider, DisabledProvider)
    assert secret.loads == []


def test_secret_is_absent_from_models_and_repr(tmp_path) -> None:
    secret_value = "top-secret-key"
    service = _service(tmp_path, secret=SecretStore(secret_value))
    settings = _settings(AiProviderId.OPENAI)

    resolution = service.save_selection(settings)

    assert secret_value not in repr(settings)
    assert secret_value not in repr(resolution)
    assert "secret" not in AiProviderSettings.__dataclass_fields__
    assert "secret" not in type(resolution).__dataclass_fields__


def test_legacy_display_label_does_not_enable_provider(tmp_path) -> None:
    service = _service(tmp_path, secret=SecretStore(fail_load=True))
    service.config.set("ai.provider", "none")  # type: ignore[attr-defined]

    changed = service.migrate_legacy_settings(
        LegacyAiProviderSettings(
            provider_label="OpenAI API",
            model="legacy-model",
            base_url="https://legacy.example.test/v1",
        )
    )
    resolution = service.resolve_provider()

    assert changed
    assert resolution.effective_provider_id is AiProviderId.DISABLED
    assert service.config.get("ai.provider") == "disabled"
    assert service.config.get("ai.model") == "legacy-model"
    assert service.config.get("ai.base_url") == "https://legacy.example.test/v1"


def test_legacy_migration_is_idempotent(tmp_path) -> None:
    service = _service(tmp_path)
    service.config.set("ai.provider", "none")  # type: ignore[attr-defined]
    legacy = LegacyAiProviderSettings("OpenAI API", "legacy-model", "https://legacy.test/v1")

    assert service.migrate_legacy_settings(legacy)
    first = service.config.snapshot()  # type: ignore[attr-defined]
    assert not service.migrate_legacy_settings(legacy)
    assert service.config.snapshot() == first  # type: ignore[attr-defined]


def test_config_manager_roundtrip_persists_stable_id(tmp_path) -> None:
    path = tmp_path / "settings.json"
    service = AiProviderSelectionService(ConfigManager(path), SecretStore("saved-key"))

    resolution = service.save_selection(_settings(AiProviderId.OPENAI_COMPATIBLE))
    loaded = ConfigManager(path)

    assert resolution.available
    assert loaded.get("ai.provider") == "openai_compatible"
    assert json.loads(path.read_text(encoding="utf-8"))["ai"]["provider"] == ("openai_compatible")
    assert "saved-key" not in path.read_text(encoding="utf-8")


def test_corrupt_ai_section_does_not_interrupt_resolution(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"ai": ["broken"]}), encoding="utf-8")
    service = AiProviderSelectionService(ConfigManager(path), SecretStore(fail_load=True))

    resolution = service.resolve_provider()

    assert isinstance(resolution.provider, DisabledProvider)
    assert resolution.available


def test_secret_save_failure_does_not_change_canonical_provider(tmp_path) -> None:
    config = ConfigManager(tmp_path / "settings.json")
    service = AiProviderSelectionService(config, SecretStore(fail_save=True))

    resolution = service.save_selection(
        _settings(AiProviderId.OPENAI),
        credential="do-not-leak",
    )

    assert resolution.effective_provider_id is AiProviderId.DISABLED
    assert config.get("ai.provider") == "disabled"
    assert "do-not-leak" not in repr(resolution)


def test_explicit_environment_override_has_priority(tmp_path) -> None:
    config = ConfigManager(tmp_path / "settings.json")
    config.set("ai.provider", "disabled")
    service = AiProviderSelectionService(
        config,
        SecretStore("saved-key"),
        environment_override=_settings(AiProviderId.OPENAI),
    )

    resolution = service.resolve_provider()

    assert resolution.effective_provider_id is AiProviderId.OPENAI
    assert config.get("ai.provider") == "disabled"


def test_saved_secret_uses_existing_keyring_name(tmp_path) -> None:
    secret = SecretStore()
    service = _service(tmp_path, secret=secret)

    resolution = service.save_selection(
        _settings(AiProviderId.OPENAI),
        credential="new-value",
    )

    assert resolution.available
    assert secret.saves == [(OPENAI_API_KEY_SECRET, "new-value")]
