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
    OLLAMA_AUTH_PLACEHOLDER,
    OLLAMA_DEFAULT_BASE_URL,
)
from app.core.config_manager import ConfigManager


@dataclass
class SecretStore:
    value: str | None = "existing-cloud-key"
    loads: list[str] = field(default_factory=list)
    saves: list[tuple[str, str]] = field(default_factory=list)
    deletes: list[str] = field(default_factory=list)

    def load(self, name: str) -> str | None:
        self.loads.append(name)
        return self.value

    def save(self, name: str, value: str) -> None:
        self.saves.append((name, value))
        self.value = value

    def delete(self, name: str) -> None:
        self.deletes.append(name)
        self.value = None


def _service(tmp_path, secret: SecretStore | None = None) -> AiProviderSelectionService:
    return AiProviderSelectionService(
        ConfigManager(tmp_path / "settings.json"),
        secret or SecretStore(),
    )


def _settings(base_url: str = OLLAMA_DEFAULT_BASE_URL) -> AiProviderSettings:
    return AiProviderSettings(AiProviderId.OLLAMA, model="qwen3:8b", base_url=base_url)


def test_ollama_stable_id_resolves_existing_adapter_without_keyring(tmp_path) -> None:
    secret = SecretStore()
    service = _service(tmp_path, secret)
    service.config.update(  # type: ignore[attr-defined]
        {"ai": {"provider": "ollama", "model": "qwen3:8b", "base_url": "http://localhost:11434"}}
    )

    resolution = service.resolve_provider()

    assert resolution.effective_provider_id is AiProviderId.OLLAMA
    assert isinstance(resolution.provider, OpenAICompatibleProvider)
    assert resolution.provider.base_url == OLLAMA_DEFAULT_BASE_URL
    assert resolution.provider.model == "qwen3:8b"
    assert resolution.provider.supports_text_format is False
    assert secret.loads == []
    assert not service.credential_available(AiProviderId.OLLAMA)
    assert secret.loads == []


def test_saving_ollama_only_persists_non_secret_settings(tmp_path) -> None:
    secret = SecretStore()
    service = _service(tmp_path, secret)

    resolution = service.save_selection(_settings(), credential="must-be-ignored")
    payload = (tmp_path / "settings.json").read_text(encoding="utf-8")

    assert resolution.available and resolution.requires_restart
    assert json.loads(payload)["ai"] == {
        "provider": "ollama",
        "model": "qwen3:8b",
        "base_url": OLLAMA_DEFAULT_BASE_URL,
    }
    assert secret.loads == []
    assert secret.saves == []
    assert secret.deletes == []
    assert "must-be-ignored" not in payload
    assert payload.count(f'"{OLLAMA_AUTH_PLACEHOLDER}"') == 1
    assert "Authorization" not in payload


@pytest.mark.parametrize(
    ("base_url", "normalized"),
    [
        ("http://localhost:11434", "http://localhost:11434/v1"),
        ("https://localhost:8443/custom/path", "https://localhost:8443/v1"),
        ("http://127.0.0.1:11434/v1/", "http://127.0.0.1:11434/v1"),
        ("http://127.42.1.9:9999/api", "http://127.42.1.9:9999/v1"),
        ("http://[::1]:11434", "http://[::1]:11434/v1"),
    ],
)
def test_loopback_urls_are_accepted_and_normalized(
    tmp_path, base_url: str, normalized: str
) -> None:
    resolution = _service(tmp_path).save_selection(_settings(base_url))

    assert resolution.available
    assert isinstance(resolution.provider, OpenAICompatibleProvider)
    assert resolution.provider.base_url == normalized


@pytest.mark.parametrize(
    "base_url",
    [
        "https://ollama.example.test:11434/v1",
        "http://192.168.1.20:11434/v1",
        "http://localhost.evil.test:11434/v1",
        "http://user:password@localhost:11434/v1",
        "http://localhost:11434/v1?token=private",
        "http://localhost:11434/v1#private",
        "ftp://localhost:11434/v1",
        "file:///tmp/ollama",
        "http://localhost:0/v1",
    ],
)
def test_non_loopback_or_unsafe_urls_degrade_safely(tmp_path, base_url: str) -> None:
    resolution = _service(tmp_path).save_selection(_settings(base_url))

    assert isinstance(resolution.provider, DisabledProvider)
    assert not resolution.available
    assert base_url not in repr(resolution)
    assert "private" not in repr(resolution)
    assert "tmp" not in repr(resolution)


def test_model_is_required_for_ollama(tmp_path) -> None:
    resolution = _service(tmp_path).save_selection(
        AiProviderSettings(AiProviderId.OLLAMA, model=" ", base_url=OLLAMA_DEFAULT_BASE_URL)
    )

    assert isinstance(resolution.provider, DisabledProvider)
    assert not resolution.available


def test_legacy_ollama_label_does_not_activate_provider(tmp_path) -> None:
    service = _service(tmp_path)
    service.config.set("ai.provider", "none")  # type: ignore[attr-defined]

    assert service.migrate_legacy_settings(
        LegacyAiProviderSettings("Ollama", "qwen3:8b", "http://localhost:11434")
    )
    assert service.resolve_provider().effective_provider_id is AiProviderId.DISABLED
    assert service.config.get("ai.provider") == "disabled"


def test_transport_targets_responses_only_when_analyze_is_called(tmp_path, monkeypatch) -> None:
    captured: dict[str, object] = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def read(self, limit: int) -> bytes:
            assert limit == 4 * 1024 * 1024 + 1
            return json.dumps(
                {
                    "id": "local-response",
                    "output": [{"content": [{"type": "output_text", "text": "local result"}]}],
                }
            ).encode("utf-8")

    def fake_urlopen(request, *, timeout):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr("app.ai.provider._open_without_redirects", fake_urlopen)
    service = _service(tmp_path)
    resolution = service.save_selection(_settings())

    assert captured == {}
    result = resolution.provider.analyze(
        "current prompt",
        ["current context"],
        output_format={"type": "json_schema", "schema": {"private": True}},
    )

    assert captured["url"] == "http://localhost:11434/v1/responses"
    assert captured["body"] == {
        "model": "qwen3:8b",
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": "current prompt"}]},
            {"role": "user", "content": [{"type": "input_text", "text": "current context"}]},
        ],
        "stream": False,
    }
    assert "text" not in captured["body"]
    assert "store" not in captured["body"]
    assert result == {"status": "ok", "text": "local result", "raw_id": "local-response"}
    assert OLLAMA_AUTH_PLACEHOLDER not in repr(result)
