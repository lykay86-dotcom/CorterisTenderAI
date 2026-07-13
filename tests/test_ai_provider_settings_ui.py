from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

from app.core.ai.provider_selection import (
    AiProviderId,
    AiProviderSelectionService,
    OPENAI_DEFAULT_BASE_URL,
)
from app.core.config_manager import ConfigManager
from app.ui.ai_provider_settings import AiProviderSettingsWidget, RESTART_NOTICE


@dataclass
class SecretStore:
    value: str | None = None
    loads: int = 0
    saves: list[tuple[str, str]] = field(default_factory=list)

    def load(self, _name: str) -> str | None:
        self.loads += 1
        return self.value

    def save(self, name: str, value: str) -> None:
        self.saves.append((name, value))
        self.value = value

    def delete(self, _name: str) -> None:
        self.value = None


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _widget(
    tmp_path, *, secret: SecretStore | None = None
) -> tuple[
    AiProviderSettingsWidget,
    ConfigManager,
    SecretStore,
]:
    _app()
    config = ConfigManager(tmp_path / "settings.json")
    store = secret or SecretStore()
    service = AiProviderSelectionService(config, store)
    return AiProviderSettingsWidget(service), config, store


def test_combo_item_data_contains_only_stable_provider_ids(tmp_path) -> None:
    widget, _config, _secret = _widget(tmp_path)

    values = [
        widget.provider_combo.itemData(index) for index in range(widget.provider_combo.count())
    ]

    assert values == ["disabled", "openai", "openai_compatible"]
    assert all("Ollama" not in widget.provider_combo.itemText(index) for index in range(3))


def test_selected_id_loads_and_saves_canonically(tmp_path, monkeypatch) -> None:
    widget, config, secret = _widget(tmp_path, secret=SecretStore("saved-key"))
    notices: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda _parent, _title, message: notices.append(message),
    )

    widget.provider_combo.setCurrentIndex(widget.provider_combo.findData("openai_compatible"))
    widget.model_edit.setText("custom-model")
    widget.base_url_edit.setText("https://ai.example.test/v1")
    result = widget.save()

    assert result is not None and result.available
    assert config.get("ai.provider") == "openai_compatible"
    assert config.get("ai.model") == "custom-model"
    assert config.get("ai.base_url") == "https://ai.example.test/v1"
    assert notices == [RESTART_NOTICE]
    assert secret.loads >= 1


def test_api_key_is_cleared_and_never_written_to_config(tmp_path, monkeypatch) -> None:
    widget, config, secret = _widget(tmp_path)
    monkeypatch.setattr(QMessageBox, "information", lambda *_args: None)
    widget.provider_combo.setCurrentIndex(widget.provider_combo.findData("openai"))
    widget.model_edit.setText("gpt-test")
    widget.credential_edit.setText("top-secret-key")
    assert widget.credential_edit.dynamicPropertyNames() == []

    result = widget.save()

    assert result is not None and result.available
    assert widget.credential_edit.text() == ""
    assert widget.credential_edit.placeholderText() == "Сохранён"
    assert secret.saves
    payload = json.dumps(config.snapshot(), ensure_ascii=False)
    assert "top-secret-key" not in payload
    assert "api_key" not in payload


def test_disabled_blocks_fields_and_does_not_read_secret(tmp_path) -> None:
    widget, _config, secret = _widget(tmp_path, secret=SecretStore("saved-key"))

    assert widget.selected_provider_id() is AiProviderId.DISABLED
    assert not widget.model_edit.isEnabled()
    assert not widget.base_url_edit.isEnabled()
    assert not widget.credential_edit.isEnabled()
    assert secret.loads == 0


def test_official_openai_locks_official_base_url(tmp_path) -> None:
    widget, _config, _secret = _widget(tmp_path)

    widget.provider_combo.setCurrentIndex(widget.provider_combo.findData("openai"))

    assert widget.model_edit.isEnabled()
    assert widget.credential_edit.isEnabled()
    assert not widget.base_url_edit.isEnabled()
    assert widget.base_url_edit.text() == OPENAI_DEFAULT_BASE_URL


def test_unknown_provider_is_presented_as_disabled(tmp_path) -> None:
    _app()
    config = ConfigManager(tmp_path / "settings.json")
    config.set("ai.provider", "unknown-provider")
    widget = AiProviderSettingsWidget(AiProviderSelectionService(config, SecretStore()))

    assert widget.selected_provider_id() is AiProviderId.DISABLED
    assert widget.provider_combo.currentData() == "disabled"


def test_saving_settings_never_executes_http_request(tmp_path, monkeypatch) -> None:
    widget, _config, _secret = _widget(tmp_path)
    monkeypatch.setattr(QMessageBox, "information", lambda *_args: None)
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("HTTP request")),
    )
    widget.provider_combo.setCurrentIndex(widget.provider_combo.findData("openai"))
    widget.model_edit.setText("gpt-test")
    widget.credential_edit.setText("saved-key")

    result = widget.save()

    assert result is not None and result.available


def test_button_is_save_only_and_restart_notice_is_explicit(tmp_path) -> None:
    widget, _config, _secret = _widget(tmp_path)

    assert widget.save_button.text() == "Сохранить"
    assert "после перезапуска" in RESTART_NOTICE
