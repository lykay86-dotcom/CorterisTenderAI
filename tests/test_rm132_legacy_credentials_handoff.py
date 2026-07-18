"""RM-132 legacy manual-platform credential retirement contract."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication, QStatusBar

from app.core.ai.provider_selection import AiProviderSelectionService
from app.ui.main_window import (
    LEGACY_PLATFORM_CREDENTIAL_NOTICE,
    TenderWorkspacePage,
)
from app.core.config_manager import ConfigManager


class EmptyAiSecretStore:
    def load(self, _name: str) -> str | None:
        return None

    def save(self, _name: str, _value: str) -> None:
        return None

    def delete(self, _name: str) -> None:
        return None


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_legacy_source_has_no_arbitrary_keyring_crud() -> None:
    source = Path("app/ui/main_window.py").read_text(encoding="utf-8")

    assert "from app.security.secrets" not in source
    assert 'save_secret(f"platform:' not in source
    assert 'load_secret(f"platform:' not in source
    assert 'delete_secret(f"platform:' not in source
    assert "не управляет credentials" in LEGACY_PLATFORM_CREDENTIAL_NOTICE.casefold()


def test_legacy_secret_input_is_disabled_and_never_prefilled(tmp_path, monkeypatch) -> None:
    _app()
    monkeypatch.setattr(
        "app.ui.pages.tender_workspace_page.UserSettingsStore",
        lambda: __import__(
            "app.config.user_settings", fromlist=["UserSettingsStore"]
        ).UserSettingsStore(tmp_path / "user_settings.json"),
    )
    monkeypatch.setattr(TenderWorkspacePage, "refresh", lambda _self: None)
    page = TenderWorkspacePage(
        ai_provider_selection_service=AiProviderSelectionService(
            ConfigManager(tmp_path / "config.json"),
            EmptyAiSecretStore(),
        ),
        status_bar=QStatusBar(),
    )

    assert page.platform_secret.text() == ""
    assert not page.platform_secret.isEnabled()
    assert "credentials" in page.platform_secret.placeholderText().casefold()
